"""
Gmail Service — IMAP reader + SMTP sender using user's Gmail App Password.

Security:
- App passwords stored encrypted with Fernet (key derived from app SECRET_KEY + salt)
- Passwords are never logged or returned in API responses
- IMAP/SMTP always use SSL/TLS

Usage:
  from app.services.gmail_service import encrypt_password, decrypt_password,
                                         fetch_inbox, send_via_mailbox, test_connection
"""
import imaplib
import smtplib
import email as _email_module
import os
import hashlib
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.header import decode_header as _decode_header
from datetime import datetime, timezone
from typing import Optional
from flask import current_app
from cryptography.fernet import Fernet

GMAIL_IMAP_HOST = 'imap.gmail.com'
GMAIL_IMAP_PORT = 993
GMAIL_SMTP_HOST = 'smtp.gmail.com'
GMAIL_SMTP_PORT = 587

APP_PASSWORD_HELP_URL = (
    'https://myaccount.google.com/apppasswords'
)


# ─── Encryption helpers ───────────────────────────────────────────────────────

def _fernet() -> Fernet:
    """Derive a stable Fernet key from the app SECRET_KEY."""
    secret = current_app.config['SECRET_KEY'].encode()
    # SHA-256 → 32 bytes → base64url → valid Fernet key
    raw = hashlib.sha256(secret + b':baunavigator:mailbox').digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def encrypt_password(plain_password: str) -> str:
    """Encrypt an app password. Returns base64 ciphertext string."""
    return _fernet().encrypt(plain_password.encode('utf-8')).decode('utf-8')


def decrypt_password(enc_password: str) -> str:
    """Decrypt an app password stored in DB."""
    return _fernet().decrypt(enc_password.encode('utf-8')).decode('utf-8')


# ─── Header decode helper ──────────────────────────────────────────────────────

def _safe_header(raw) -> str:
    if raw is None:
        return ''
    parts = _decode_header(raw)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(enc or 'utf-8', errors='replace'))
            except Exception:
                decoded.append(part.decode('utf-8', errors='replace'))
        else:
            decoded.append(str(part))
    return ' '.join(decoded)


# ─── Connection test ──────────────────────────────────────────────────────────

def test_connection(gmail_address: str, app_password: str) -> dict:
    """
    Test IMAP connection with given credentials.
    Returns: {'success': bool, 'error': str|None}
    """
    try:
        mail = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
        mail.login(gmail_address, app_password)
        mail.logout()
        return {'success': True, 'error': None}
    except imaplib.IMAP4.error as e:
        return {'success': False, 'error': str(e)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ─── Inbox fetch ──────────────────────────────────────────────────────────────

def fetch_inbox(mailbox, limit: int = 30) -> dict:
    """
    Fetch latest emails from Gmail inbox.
    mailbox: ProjectMailbox instance
    Returns: {'success': bool, 'emails': list, 'error': str|None}
    """
    try:
        pwd = decrypt_password(mailbox.app_password_enc)
        conn = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
        conn.login(mailbox.gmail_address, pwd)
        conn.select('INBOX')

        _typ, data = conn.search(None, 'ALL')
        ids = data[0].split()
        # Newest first, limited
        ids = ids[-limit:][::-1]

        emails = []
        for uid in ids:
            _typ, msg_data = conn.fetch(uid, '(RFC822)')
            if not msg_data or msg_data[0] is None:
                continue
            raw = msg_data[0][1]
            msg = _email_module.message_from_bytes(raw)

            subject = _safe_header(msg.get('Subject', ''))
            sender  = _safe_header(msg.get('From', ''))
            date_str = msg.get('Date', '')

            # Parse date
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_str)
                date_iso = dt.isoformat()
            except Exception:
                date_iso = date_str

            # Extract body and attachments
            body_text = ''
            body_html = ''
            attachments = []

            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    cd = str(part.get('Content-Disposition', ''))
                    if 'attachment' in cd:
                        fname = part.get_filename()
                        if fname:
                            attachments.append({
                                'filename': _safe_header(fname),
                                'content_type': ct,
                                'size': len(part.get_payload(decode=True) or b''),
                                'uid': uid.decode(),
                                'part_index': msg.walk().__class__,  # indicator only
                            })
                    elif ct == 'text/plain' and not body_text:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset('utf-8')
                            body_text = payload.decode(charset, errors='replace')[:2000]
                    elif ct == 'text/html' and not body_html:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset('utf-8')
                            body_html = payload.decode(charset, errors='replace')[:2000]
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset('utf-8')
                    body_text = payload.decode(charset, errors='replace')[:2000]

            emails.append({
                'uid': uid.decode(),
                'subject': subject,
                'from': sender,
                'date_iso': date_iso,
                'body': body_text or '(HTML-Nachricht — im Browser öffnen)',
                'has_html': bool(body_html),
                'attachments': attachments,
                'read': b'\\Seen' in (msg.get('Flags', b'') or b''),
            })

        conn.logout()

        # Update sync timestamp
        from app import db
        from app.models.models import now_utc
        mailbox.last_sync_at = now_utc()
        mailbox.email_count = len(ids)
        db.session.commit()

        return {'success': True, 'emails': emails, 'error': None}

    except imaplib.IMAP4.error as e:
        return {'success': False, 'emails': [], 'error': f'IMAP Fehler: {e}'}
    except Exception as e:
        return {'success': False, 'emails': [], 'error': str(e)}


# ─── Fetch single email with attachments as bytes ─────────────────────────────

def fetch_email_attachments(mailbox, uid: str) -> dict:
    """
    Fetch all attachment bytes from a specific email by UID.
    Returns: {'success': bool, 'attachments': [{filename, data, content_type}]}
    """
    try:
        pwd = decrypt_password(mailbox.app_password_enc)
        conn = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
        conn.login(mailbox.gmail_address, pwd)
        conn.select('INBOX')

        _typ, msg_data = conn.fetch(uid.encode(), '(RFC822)')
        conn.logout()

        if not msg_data or msg_data[0] is None:
            return {'success': False, 'attachments': [], 'error': 'E-Mail nicht gefunden'}

        msg = _email_module.message_from_bytes(msg_data[0][1])
        attachments = []

        for part in msg.walk():
            cd = str(part.get('Content-Disposition', ''))
            if 'attachment' in cd:
                fname = part.get_filename()
                data = part.get_payload(decode=True)
                if fname and data:
                    attachments.append({
                        'filename': _safe_header(fname),
                        'data': data,
                        'content_type': part.get_content_type(),
                    })

        return {'success': True, 'attachments': attachments, 'error': None}
    except Exception as e:
        return {'success': False, 'attachments': [], 'error': str(e)}


# ─── Send email ──────────────────────────────────────────────────────────────

def send_via_mailbox(
    mailbox,
    to_email: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    reply_to: Optional[str] = None,
    attachments: Optional[list] = None,  # list of {'filename': str, 'data': bytes, 'content_type': str}
) -> dict:
    """
    Send email via project Gmail mailbox using SMTP + TLS.
    Returns: {'success': bool, 'error': str|None}
    """
    try:
        pwd = decrypt_password(mailbox.app_password_enc)
        sender = mailbox.gmail_address

        msg = MIMEMultipart('alternative') if not attachments else MIMEMultipart('mixed')
        msg['From'] = sender
        msg['To'] = to_email
        msg['Subject'] = subject
        if cc:
            msg['Cc'] = cc
        if reply_to:
            msg['Reply-To'] = reply_to

        # Body — try plain text first, then HTML detection
        if '<html' in body.lower() or '<br' in body.lower():
            msg.attach(MIMEText(body, 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Attachments
        if attachments:
            for att in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(att['data'])
                encoders.encode_base64(part)
                safe_name = att['filename'].replace('\n', '').replace('\r', '')
                part.add_header('Content-Disposition', 'attachment', filename=safe_name)
                msg.attach(part)

        recipients = [to_email]
        if cc:
            recipients.append(cc)

        with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, pwd)
            server.sendmail(sender, recipients, msg.as_string())

        return {'success': True, 'error': None}

    except smtplib.SMTPAuthenticationError:
        return {
            'success': False,
            'error': 'Authentifizierung fehlgeschlagen — App-Passwort prüfen.'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
