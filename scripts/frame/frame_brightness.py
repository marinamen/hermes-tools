#!/usr/bin/env python3
"""
Samsung The Frame — ajuste de brillo según hora del día.
Mañana 50, tarde degrada de 50→10, noche 10.
Ejecutado cada 30 min por cron Hermes (no_agent → cero tokens).
"""
import sys, os, datetime

sys.path.insert(0, '/Users/sitamendieta/Library/Python/3.9/lib/python/site-packages')
from samsungtvws.art import SamsungTVArt

import signal
def _timeout_handler(signum, frame):
    print("⏱️  Timeout — TV no responde a tiempo")
    raise SystemExit(1)
signal.signal(signal.SIGALRM, _timeout_handler)
signal.alarm(45)  # 45s hard limit


TV_IP = os.getenv('FRAME_TV_IP', '192.168.0.26')
TV_PORT = 8001
BASE = os.path.expanduser('~/Gits/frame-control')
TOKEN_FILE = os.path.join(BASE, 'state', 'samsung_token2.txt')

now = datetime.datetime.now()
hour, minute = now.hour, now.minute

if hour < 8 or hour >= 23:
    target, period = 10, "noche"
elif hour < 21:
    target, period = 50, "día"
else:
    elapsed = (hour - 21) + minute / 60.0
    target = max(10, min(50, int(round(50 - 40 * elapsed / 2.0))))
    period = "transición noche"

print(f"[{now.strftime('%Y-%m-%d %H:%M')}] {period} → brillo objetivo: {target}")

try:
    art = SamsungTVArt(TV_IP, port=TV_PORT, token_file=TOKEN_FILE, timeout=15)
    art.open()
    current = art.get_brightness()
    if str(current) != str(target):
        art.set_brightness(target)
        print(f"✅ {current} → {target}")
    else:
        print(f"Sin cambios ({target})")
    art.close()
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
