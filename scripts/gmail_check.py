#!/usr/bin/env python3
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re

ENV_PATH = Path('/home/marti/.openclaw/workspace/.env')
STATE_PATH = Path('/home/marti/.openclaw/workspace/memory/gmail-state.json')

IMPORTANT_SENDERS = [
    'accounts.google.com',
    'github.com',
    'notice.xiaomi.com',
    'no-reply@accounts.google.com',
]
IMPORTANT_SUBJECT_KEYWORDS = [
    'alert bezpieczeństwa',
    'security alert',
    'verification',
    '2fa',
    'login',
    'hasło',
    'password',
    'payment',
    'invoice',
    'faktura',
]


def load_env(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


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


def is_important(msg: dict) -> bool:
    sender = (msg.get('from') or '').lower()
    subject = (msg.get('subject') or '').lower()
    if any(s in sender for s in IMPORTANT_SENDERS):
        return True
    if any(k in subject for k in IMPORTANT_SUBJECT_KEYWORDS):
        return True
    return False


def main():
    load_env(ENV_PATH)
    user = os.getenv('GMAIL_USER')
    pwd = os.getenv('GMAIL_APP_PASSWORD')
    if not user or not pwd:
        raise SystemExit('Brak GMAIL_USER lub GMAIL_APP_PASSWORD w .env')

    prev = load_state(STATE_PATH)
    seen_ids = set(prev.get('seenIds', []))

    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(user, pwd)
    mail.select('INBOX')

    status, data = mail.search(None, '(UNSEEN)')
    if status != 'OK':
        raise SystemExit('Nie udało się pobrać UNSEEN')

    ids = data[0].split()
    ids = ids[-80:]  # recent window

    messages = []
    for msg_id in reversed(ids):
        st, msg_data = mail.fetch(msg_id, '(RFC822)')
        if st != 'OK' or not msg_data or not msg_data[0]:
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        subject = re.sub(r'\s+', ' ', decode_mime(msg.get('Subject', '')).strip())
        from_ = re.sub(r'\s+', ' ', decode_mime(msg.get('From', '')).strip())
        date_ = msg.get('Date', '')
        item = {'id': msg_id.decode(), 'from': from_, 'subject': subject, 'date': date_}
        messages.append(item)

    unread_ids = {m['id'] for m in messages}
    new_unread = [m for m in messages if m['id'] not in seen_ids]
    important_new = [m for m in new_unread if is_important(m)]

    # update seen ids with current unread set + previous (bounded)
    merged = list((seen_ids | unread_ids))
    merged = merged[-5000:]

    payload = {
        'checkedAt': datetime.now(timezone.utc).isoformat(),
        'unreadCount': len(data[0].split()),
        'newUnreadCount': len(new_unread),
        'importantNewCount': len(important_new),
        'importantNew': important_new[:15],
        'latest': messages[:15],
        'seenIds': merged,
    }

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    mail.logout()


if __name__ == '__main__':
    main()
