#!/usr/bin/env python3
import imaplib, os, email, json, re
from pathlib import Path
from email.header import decode_header
from datetime import datetime, timezone

ENV = Path('/home/marti/.openclaw/workspace/.env')
OUT = Path('/home/marti/.openclaw/workspace/memory/gmail-ing-alerts.json')

ING_FROM_PATTERNS = [
    'ing.pl',
    'ingbank',
    'ingbsk',
]
ING_SUBJECT_PATTERNS = [
    'ing',
    'transakc',
    'płatno',
    'platno',
    'przelew',
    'karta',
    'blik',
    'saldo',
    'rachunek',
]


def load_env():
    for l in ENV.read_text(encoding='utf-8').splitlines():
        if '=' in l and not l.strip().startswith('#'):
            k, v = l.split('=', 1)
            os.environ[k.strip()] = v.strip()


def dec(v: str) -> str:
    out = ''
    for t, e in decode_header(v or ''):
        out += t.decode(e or 'utf-8', 'replace') if isinstance(t, bytes) else t
    return re.sub(r'\s+', ' ', out).strip()


def looks_like_ing(frm: str, subj: str) -> bool:
    f = frm.lower()
    s = subj.lower()
    return any(p in f for p in ING_FROM_PATTERNS) or any(p in s for p in ING_SUBJECT_PATTERNS)


def main():
    load_env()
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(os.environ['GMAIL_USER'], os.environ['GMAIL_APP_PASSWORD'])
    mail.select('INBOX')

    st, d = mail.search(None, 'UNSEEN')
    ids = d[0].split() if st == 'OK' and d and d[0] else []

    hits = []
    for mid in ids[-300:]:
        st2, resp = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
        if st2 != 'OK' or not resp or not resp[0]:
            continue
        msg = email.message_from_bytes(resp[0][1])
        frm = dec(msg.get('From', ''))
        subj = dec(msg.get('Subject', ''))
        date = dec(msg.get('Date', ''))
        if looks_like_ing(frm, subj):
            hits.append({'id': mid.decode(), 'from': frm, 'subject': subj, 'date': date})

    out = {
        'checkedAt': datetime.now(timezone.utc).isoformat(),
        'ingUnreadCount': len(hits),
        'ingUnread': hits[:30]
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    mail.logout()


if __name__ == '__main__':
    main()
