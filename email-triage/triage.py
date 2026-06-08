#!/usr/bin/env python3
"""
email-triage: a minimal IMAP email categorizer using Anthropic Claude.

Connects to any IMAP server, fetches unread emails, asks Claude to classify
each one into a category (Personal, Work, Bills, Newsletter, Spam, Other),
and prints a short summary to stdout. Optionally moves them to category folders.

Usage:
    export EMAIL_USER=you@example.com
    export EMAIL_PASSWORD=app-password
    export IMAP_HOST=imap.example.com
    export ANTHROPIC_API_KEY=sk-ant-...
    python triage.py
    python triage.py --move   # also moves emails to "Triage/{Category}" folders
    python triage.py --limit 10
"""
import argparse
import email
import imaplib
import json
import os
import sys
from email.header import decode_header
from email.utils import parseaddr

try:
    import anthropic
except ImportError:
    print("Install: pip install anthropic", file=sys.stderr)
    sys.exit(1)

CATEGORIES = ["Personal", "Work", "Bills", "Newsletter", "Spam", "Other"]
MODEL = "claude-3-5-haiku-20241022"  # cheap and fast for classification


def decode_h(value: str) -> str:
    """Decode an RFC 2047 encoded header into plain str."""
    if not value:
        return ""
    parts = decode_header(value)
    out = ""
    for text, charset in parts:
        if isinstance(text, bytes):
            try:
                out += text.decode(charset or "utf-8", errors="replace")
            except LookupError:
                out += text.decode("utf-8", errors="replace")
        else:
            out += text
    return out.strip()


def get_body(msg, limit: int = 1500) -> str:
    """Extract plain-text body, capped at `limit` characters."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )
                    return body[:limit]
                except Exception:
                    continue
    else:
        try:
            body = msg.get_payload(decode=True).decode(
                msg.get_content_charset() or "utf-8", errors="replace"
            )
            return body[:limit]
        except Exception:
            return ""
    return ""


def classify(client: anthropic.Anthropic, sender: str, subject: str, body: str) -> dict:
    """Ask Claude to classify and summarize one email."""
    prompt = f"""Classify this email and write a one-sentence summary.

From: {sender}
Subject: {subject}
Body (truncated): {body[:1500]}

Respond with JSON only:
{{"category": "<one of: {', '.join(CATEGORIES)}>", "summary": "<one short sentence>"}}"""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    # Strip ```json fences if Claude wraps the output
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"category": "Other", "summary": text[:100]}


def ensure_folder(imap: imaplib.IMAP4_SSL, name: str) -> None:
    """Create folder if missing (silently no-op if it already exists)."""
    try:
        imap.create(f'"{name}"')
    except imaplib.IMAP4.error:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--move", action="store_true",
                    help="Move emails into Triage/<Category> folders.")
    ap.add_argument("--limit", type=int, default=20,
                    help="Max emails to process (default 20).")
    ap.add_argument("--folder", default="INBOX",
                    help="Source IMAP folder (default INBOX).")
    args = ap.parse_args()

    user = os.environ["EMAIL_USER"]
    pwd = os.environ["EMAIL_PASSWORD"]
    host = os.environ["IMAP_HOST"]
    port = int(os.environ.get("IMAP_PORT", "993"))

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    imap = imaplib.IMAP4_SSL(host, port)
    imap.login(user, pwd)
    imap.select(args.folder)

    _typ, data = imap.search(None, "UNSEEN")
    uids = data[0].split()[:args.limit]
    print(f"Found {len(uids)} unread emails in {args.folder}", file=sys.stderr)

    for uid in uids:
        _typ, raw = imap.fetch(uid, "(RFC822)")
        if not raw or not raw[0]:
            continue
        msg = email.message_from_bytes(raw[0][1])
        sender = parseaddr(decode_h(msg.get("From", "")))[1] or "(unknown)"
        subject = decode_h(msg.get("Subject", "(no subject)"))
        body = get_body(msg)

        try:
            result = classify(client, sender, subject, body)
        except Exception as e:
            print(f"⚠️  Skipped UID {uid.decode()}: {e}", file=sys.stderr)
            continue

        cat = result.get("category", "Other")
        summary = result.get("summary", "")
        print(f"[{cat:10s}] {sender:30s}  {subject[:50]:50s}  →  {summary}")

        if args.move and cat in CATEGORIES:
            folder = f"Triage/{cat}"
            ensure_folder(imap, folder)
            imap.copy(uid, folder)
            imap.store(uid, "+FLAGS", "\\Deleted")

    if args.move:
        imap.expunge()
    imap.logout()
    return 0


if __name__ == "__main__":
    sys.exit(main())
