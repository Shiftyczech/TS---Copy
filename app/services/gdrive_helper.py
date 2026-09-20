"""
Google Drive helper – upload/download backup ZIPs via Google Drive API
"""
import os

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_NAME = "TS_Skleniky_Backup"


class GDriveHelper:
    def __init__(self, ctx):
        self.ctx = ctx
        self.creds_path = os.path.join(ctx.app_dir, "credentials.json")
        self.token_path = os.path.join(ctx.app_dir, "token.json")
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service

        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                from google.auth.exceptions import RefreshError
                try:
                    creds.refresh(Request())
                except RefreshError:
                    creds = None
            
            if not creds or not creds.valid:
                if not os.path.exists(self.creds_path):
                    raise FileNotFoundError(
                        "Soubor credentials.json nenalezen. "
                        "Stáhněte ho z Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(self.creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
                
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def _get_or_create_folder(self):
        service = self._get_service()
        results = service.files().list(
            q=f"name='{FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces="drive", fields="files(id, name)"
        ).execute()
        files = results.get("files", [])
        if files:
            return files[0]["id"]

        meta = {
            "name": FOLDER_NAME,
            "mimeType": "application/vnd.google-apps.folder"
        }
        folder = service.files().create(body=meta, fields="id").execute()
        return folder["id"]

    def upload(self, filepath, progress_cb=None):
        from googleapiclient.http import MediaFileUpload

        service = self._get_service()
        folder_id = self._get_or_create_folder()
        filename = os.path.basename(filepath)

        media = MediaFileUpload(filepath, resumable=True)
        meta = {"name": filename, "parents": [folder_id]}

        request = service.files().create(body=meta, media_body=media, fields="id")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status and progress_cb:
                progress_cb(int(status.progress() * 100))
        if progress_cb:
            progress_cb(100)
        return response.get("id")

    def download_latest(self, dest_dir, progress_cb=None):
        from googleapiclient.http import MediaIoBaseDownload
        import io

        service = self._get_service()
        folder_id = self._get_or_create_folder()

        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            orderBy="createdTime desc", pageSize=1,
            fields="files(id, name)"
        ).execute()
        files = results.get("files", [])
        if not files:
            raise FileNotFoundError("Žádná záloha na Google Drive nenalezena.")

        file_id = files[0]["id"]
        file_name = files[0]["name"]
        dest_path = os.path.join(dest_dir, file_name)

        request = service.files().get_media(fileId=file_id)
        with open(dest_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status and progress_cb:
                    progress_cb(int(status.progress() * 100))
        if progress_cb:
            progress_cb(100)
        return dest_path
