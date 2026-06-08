# email-triage

Minimal IMAP email categorizer using Anthropic Claude.

Connects to any IMAP server, fetches unread emails, asks Claude to classify each one (Personal / Work / Bills / Newsletter / Spam / Other), prints a summary, and optionally moves them to `Triage/<Category>` folders.

## Setup

```bash
pip install anthropic
```

Set env vars:

```bash
export EMAIL_USER=you@example.com
export EMAIL_PASSWORD='your-app-password'   # Gmail/Yahoo app password, not your real one
export IMAP_HOST=imap.gmail.com
export IMAP_PORT=993                         # default
export ANTHROPIC_API_KEY=sk-ant-...
```

Common hosts:
- Gmail: `imap.gmail.com`
- Yahoo: `imap.mail.yahoo.com`
- Outlook: `outlook.office365.com`
- iCloud: `imap.mail.me.com`

## Usage

Dry run (just classify, print summary):
```bash
python triage.py
python triage.py --limit 50
python triage.py --folder Archive
```

Move into category folders:
```bash
python triage.py --move
```

This creates a `Triage/` mailbox with subfolders for each category.

## Cost

Uses `claude-3-5-haiku-20241022` (~$0.001 per email). 100 emails ≈ $0.10.

For more accurate triage, edit `MODEL = "claude-3-5-sonnet-..."` (~10× cost).

## How it works

1. Connect via `imaplib` (no OAuth — uses an app password)
2. Fetch unread emails (UNSEEN flag)
3. Extract `From`, `Subject`, and first 1500 chars of plain-text body
4. Ask Claude to classify + summarize in JSON
5. (Optional) `imap.copy` + `\Deleted` + `expunge` to move

## Limitations

- IMAP only (no Gmail API)
- App passwords only (no OAuth flow)
- Plain text bodies only (HTML attachments skipped)
- One classification per email (no labels)

## License

MIT — see `../LICENSE`.
