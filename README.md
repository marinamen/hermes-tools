# hermes-tools

Tools and scripts for [Hermes Agent](https://github.com/NousResearch/hermes-agent)-built while extending my family's home assistant setup. Built with pytorch

## What's here

### `scripts/frame/`
Control scripts for Samsung The Frame TV (Art Mode):
- `frame_carousel.py` — rotate through a JSON list of art-mode image IDs
- `frame_brightness.py` — auto-adjust brightness by time of day
- `frame_watchdog.py` — Wake-on-LAN if TV goes to standby
- `frame_refresh_random.py` — pick a random year of photos, detect faces, fit them to the screen, add date overlay, and upload to the Frame

Set up env:
```bash
export FRAME_TV_IP=192.168.x.x
export FRAME_TV_MAC=AA:BB:CC:DD:EE:FF
```

Needs `samsungtvws[encrypted]` and a paired token at `~/Gits/frame-control/state/samsung_token2.txt`.

### `scripts/photos/`
Photo archive organization:
- `organize_by_date.py` — sort photos into `YYYY/YYYY-MM-Mes/` from EXIF
- `restructure_with_heic.py` — same but also re-encode JPG→HEIC for storage savings

Set `SOURCE_DIR` env var to your external drive path.

### `email-triage/`
Minimal IMAP email categorizer powered by Anthropic Claude. Reads unread emails from any IMAP server, classifies them (Personal / Work / Bills / Newsletter / Spam / Other), prints summaries, and optionally moves them into category folders. See `email-triage/README.md` for setup.

## Author

Marina Mendieta — [@marinamen](https://github.com/marinamen)

## License

MIT
