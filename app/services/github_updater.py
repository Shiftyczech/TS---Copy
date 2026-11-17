"""
GitHub Releases Auto-Updater for TS Skleníky.
Checks for latest release on GitHub, downloads the new .exe, and seamlessly restarts the application.
"""
import os
import sys
import json
import urllib.request
import urllib.error
from typing import Optional, Callable
from app.version import APP_VERSION, GITHUB_REPO


def parse_version(v_str: str) -> tuple[int, ...]:
    """Parse semver string like 'v1.2.3' or '1.2' to integer tuple for comparison."""
    clean = v_str.strip().lstrip("vV")
    parts = []
    for p in clean.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


def cleanup_old_executable():
    """Remove leftover .old executable from previous update if present."""
    if not getattr(sys, "frozen", False):
        return
    try:
        app_dir = os.path.dirname(sys.executable)
        base_name = os.path.basename(sys.executable)
        for fname in os.listdir(app_dir):
            if fname.startswith(base_name + ".old"):
                try:
                    os.remove(os.path.join(app_dir, fname))
                except Exception:
                    pass
    except Exception:
        pass


class UpdateInfo:
    def __init__(self, has_update: bool, latest_version: str, download_url: str,
                 asset_name: str, asset_size: int, release_notes: str = ""):
        self.has_update = has_update
        self.latest_version = latest_version
        self.download_url = download_url
        self.asset_name = asset_name
        self.asset_size = asset_size
        self.release_notes = release_notes


def _safe_urlopen(req, timeout: int = 30):
    """Open URL with automatic fallback to unverified SSL context if system root certificates fail."""
    import ssl
    try:
        ctx = ssl.create_default_context()
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    except (ssl.SSLError, urllib.error.URLError, Exception):
        ctx = ssl._create_unverified_context()
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def check_for_updates() -> Optional[UpdateInfo]:
    """Check GitHub API for the latest release."""
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": "TS-Evidence-Skleniky",
            "Accept": "application/vnd.github.v3+json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
    )

    try:
        with _safe_urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        # Connection error, offline, or rate limited
        print(f"Update check error: {e}")
        return None

    tag = data.get("tag_name", "")
    latest_ver = tag.lstrip("vV").strip()
    notes = data.get("body", "")

    # Compare versions
    if parse_version(latest_ver) <= parse_version(APP_VERSION):
        return UpdateInfo(False, latest_ver, "", "", 0, notes)

    # Find .exe asset
    assets = data.get("assets", [])
    target_asset = None
    for a in assets:
        name = a.get("name", "").lower()
        if name.endswith(".exe"):
            target_asset = a
            # Prefer matching "evidence" in name
            if "evidence" in name:
                break

    if not target_asset:
        return UpdateInfo(False, latest_ver, "", "", 0, notes)

    dl_url = target_asset.get("browser_download_url", "")
    size = target_asset.get("size", 0)
    asset_name = target_asset.get("name", "EvidenceSkleniku.exe")

    return UpdateInfo(
        has_update=True,
        latest_version=latest_ver,
        download_url=dl_url,
        asset_name=asset_name,
        asset_size=size,
        release_notes=notes
    )


def download_and_install_update(download_url: str, progress_callback: Optional[Callable[[int], None]] = None) -> bool:
    """Download new executable and swap with current running executable."""
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Aktualizace je dostupná pouze pro zkompilovanou .exe aplikaci.")

    target_exe = sys.executable
    app_dir = os.path.dirname(target_exe)
    temp_new_exe = os.path.join(app_dir, "_new_version.tmp")

    req = urllib.request.Request(
        download_url,
        headers={"User-Agent": "TS-Evidence-Skleniky"}
    )

    try:
        with _safe_urlopen(req, timeout=60) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 64 * 1024

            with open(temp_new_exe, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and progress_callback:
                        pct = int((downloaded / total_size) * 100)
                        progress_callback(min(pct, 99))

            # Verify that download was not severed prematurely
            if total_size > 0 and downloaded < total_size:
                raise RuntimeError(
                    f"Stahování aktualizace bylo přerušeno (staženo {downloaded} z {total_size} bajtů). Zkuste to prosím znovu."
                )
            if downloaded < 5 * 1024 * 1024:
                raise RuntimeError(
                    f"Stažený soubor je nekompletní nebo poškozený ({downloaded} bajtů). Zkuste to prosím znovu."
                )

        if progress_callback:
            progress_callback(100)

        # Atomic swap on Windows: rename running .exe to .old, move .tmp into place
        import time
        old_exe = target_exe + ".old"
        if os.path.exists(old_exe):
            for _ in range(5):
                try:
                    os.remove(old_exe)
                    break
                except Exception:
                    time.sleep(0.3)

        # If old_exe is still locked, use a timestamped backup name
        if os.path.exists(old_exe):
            old_exe = f"{target_exe}.old.{int(time.time())}"

        # Rename current running .exe (Windows allows renaming running binaries)
        renamed = False
        for i in range(6):
            try:
                os.rename(target_exe, old_exe)
                renamed = True
                break
            except Exception:
                if i == 5:
                    raise
                time.sleep(0.4)

        # Move downloaded .tmp into target_exe position
        for i in range(6):
            try:
                if hasattr(os, "replace"):
                    os.replace(temp_new_exe, target_exe)
                else:
                    os.rename(temp_new_exe, target_exe)
                break
            except Exception:
                if i == 5:
                    # If moving failed, try to restore original exe
                    if renamed and os.path.exists(old_exe):
                        try:
                            os.rename(old_exe, target_exe)
                        except Exception:
                            pass
                    raise
                time.sleep(0.4)

        # File swap successfully finished. Return True so caller on GUI thread can restart cleanly.
        return True
    except Exception:
        # Clean up temporary downloaded file if anything went wrong
        if os.path.exists(temp_new_exe):
            try:
                os.remove(temp_new_exe)
            except Exception:
                pass
        raise
