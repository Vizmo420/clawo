#!/usr/bin/env python3
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timezone
from pathlib import Path
import json
import os

ENV_PATH = Path('/home/marti/.openclaw/workspace/.env')
STATE_PATH = Path('/home/marti/.openclaw/workspace/memory/gmail-state.json')


def load_env(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())


def decode_mime(value: str) -> str:
    if not value:
        return ''
    parts = decode_header(value)
    out = []
    for txt, enc in parts:
        if isinstance(txt, bytes):
            out.append(txt.decode(enc or 'utf-8', errors='replace'))
        else:
            out.append(txt)
    return ''.join(out)


def main():
    load_env(ENV_PATH)
    user = os.getenv('GMAIL_USER')
    pwd = os.getenv('GMAIL_APP_PASSWORD')
    if not user or not pwd:
        raise SystemExit('Brak GMAIL_USER lub GMAIL_APP_PASSWORD w .env')

    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(user, pwd)
    mail.select('INBOX')

    # Last 20 unread, newest first
    status, data = mail.search(None, '(UNSEEN)')
    if status != 'OK':
        raise SystemExit('Nie udało się pobrać UNSEEN')

    ids = data[0].split()
    ids = ids[-20:]

    messages = []
    for msg_id in reversed(ids):
        st, msg_data = mail.fetch(msg_id, '(RFC822)')
        if st != 'OK' or not msg_data or not msg_data[0]:
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        subject = decode_mime(msg.get('Subject', ''))
        from_ = decode_mime(msg.get('From', ''))
        date_ = msg.get('Date', '')
        messages.append({'id': msg_id.decode(), 'from': from_, 'subject': subject, 'date': date_})

    payload = {
        'checkedAt': datetime.now(timezone.utc).isoformat(),
        'unreadCount': len(data[0].split()),
        'latest': messages[:10],
    }

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    mail.logout()


if __name__ == '__main__':
    main()
