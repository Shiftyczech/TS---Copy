"""
Email compose dialog – Popup for composing/sending email
1:1 layout: Pošt.server, Odesílatel, E-mail, Příjemce, Víc, body, Přílohy
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QMessageBox
)


class EmailComposeDialog(QDialog):
    def __init__(self, ctx, recipient="", subject="", body="", parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Elektronická pošta")
        self.setMinimumSize(700, 460)
        self.resize(700, 460)
        self._build_ui()
        self._load_config()
        if recipient:
            self.edit_prijemce.setText(recipient)
        if subject:
            self.edit_predmet.setText(subject)
        if body:
            self.txt_body.setPlainText(body)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Row: Pošt.server
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Pošt.server:"))
        self.edit_server = QLineEdit()
        self.edit_server.setReadOnly(True)
        row1.addWidget(self.edit_server)
        layout.addLayout(row1)

        # Row: Odesílatel + E-mail
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Odesílatel:"))
        self.edit_odesilatel = QLineEdit()
        self.edit_odesilatel.setReadOnly(True)
        row2.addWidget(self.edit_odesilatel)
        row2.addSpacing(20)
        row2.addWidget(QLabel("E-mail:"))
        self.edit_email_from = QLineEdit()
        self.edit_email_from.setReadOnly(True)
        row2.addWidget(self.edit_email_from)
        layout.addLayout(row2)

        layout.addSpacing(10)

        # Row: Příjemce + ... + Podepsat + Odeslat
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Příjemce:"))
        self.edit_prijemce = QLineEdit()
        row3.addWidget(self.edit_prijemce)
        self.btn_browse_prijemce = QPushButton("...")
        self.btn_browse_prijemce.setMaximumWidth(30)
        row3.addWidget(self.btn_browse_prijemce)
        self.btn_podepsat = QPushButton("Podepsat")
        row3.addWidget(self.btn_podepsat)
        self.btn_odeslat = QPushButton("Odeslat")
        self.btn_odeslat.setObjectName("accentButton")
        row3.addWidget(self.btn_odeslat)
        layout.addLayout(row3)

        # Row: Předmět
        row_predmet = QHBoxLayout()
        row_predmet.addWidget(QLabel("Předmět:"))
        self.edit_predmet = QLineEdit()
        row_predmet.addWidget(self.edit_predmet)
        layout.addLayout(row_predmet)

        # Row: Víc + Zpět
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Víc:"))
        self.edit_vic = QLineEdit()
        row4.addWidget(self.edit_vic)
        row4.addStretch()
        self.btn_zpet = QPushButton("Zpět")
        self.btn_zpet.setObjectName("dangerButton")
        row4.addWidget(self.btn_zpet)
        layout.addLayout(row4)

        # Body
        self.txt_body = QTextEdit()
        layout.addWidget(self.txt_body, stretch=3)

        # Přílohy
        row_prilohy = QHBoxLayout()
        row_prilohy.addWidget(QLabel("Přílohy"))
        self.txt_prilohy = QTextEdit()
        self.txt_prilohy.setMaximumHeight(60)
        row_prilohy.addWidget(self.txt_prilohy)
        self.btn_browse_prilohy = QPushButton("...")
        self.btn_browse_prilohy.setMaximumWidth(30)
        row_prilohy.addWidget(self.btn_browse_prilohy)
        layout.addLayout(row_prilohy)

        # Connections
        self.btn_odeslat.clicked.connect(self._send)
        self.btn_zpet.clicked.connect(self.reject)
        self.btn_podepsat.clicked.connect(self._sign)

    def _load_config(self):
        cfg = self.ctx.db.get_first_record("tsd00")
        if cfg:
            self.edit_server.setText(str(cfg.get("POSTSERVER", "")))
            self.edit_odesilatel.setText(str(cfg.get("ODESILATEL", "")))
            self.edit_email_from.setText(str(cfg.get("MAIL", "")))

    def _sign(self):
        cfg = self.ctx.db.get_first_record("tsd00")
        if cfg:
            name = str(cfg.get("ODESILATEL", ""))
            current = self.txt_body.toPlainText()
            self.txt_body.setPlainText(current + "\n\n" + name)

    def _send(self):
        from app.services.email_service import EmailService
        svc = EmailService(self.ctx.db)
        try:
            ok = svc.send_direct(
                to=self.edit_prijemce.text().strip(),
                subject=self.edit_predmet.text().strip(),
                body=self.txt_body.toPlainText(),
                cc=self.edit_vic.text().strip()
            )
            if ok:
                QMessageBox.information(self, "Odesláno", "E-mail byl odeslán.")
                self.accept()
            else:
                QMessageBox.warning(self, "Chyba", "Odeslání se nezdařilo.")
        except Exception as e:
            QMessageBox.warning(self, "Chyba", f"Odeslání se nezdařilo:\n{str(e)}")
