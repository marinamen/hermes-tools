#!/usr/bin/env python3
"""
Samsung The Frame — avanza una imagen del carrusel activo.
Ejecutado cada 30 min por cron Hermes (no_agent).
"""
import sys, os, json, time

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
CAROUSEL_FILE = os.path.join(BASE, 'scripts', 'frame_carousel_active.json')
INDEX_FILE = os.path.join(BASE, 'state', 'frame_carousel_index.txt')
LAST_IMAGE_FILE = os.path.join(BASE, 'state', 'frame_last_image.txt')

try:
    images = json.load(open(CAROUSEL_FILE))
except Exception as e:
    print(f"❌ Carousel file: {e}")
    sys.exit(1)

try:
    idx = int(open(INDEX_FILE).read().strip())
except Exception:
    idx = 0

next_idx = (idx + 1) % len(images)
next_image = images[next_idx]

MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        art = SamsungTVArt(TV_IP, port=TV_PORT, token_file=TOKEN_FILE, timeout=15)
        art.open()
        time.sleep(1)
        mode = art.get_artmode()
        if mode == 'on':
            art.select_image(next_image, show=True)
            open(INDEX_FILE, 'w').write(str(next_idx))
            open(LAST_IMAGE_FILE, 'w').write(next_image)
            print(f"✅ {next_idx+1}/{len(images)} → {next_image}")
        else:
            print(f"Modo arte off ({mode}), sin cambio")
        art.close()
        break
    except Exception as e:
        msg = str(e)[:120]
        print(f"Intento {attempt+1}/{MAX_RETRIES}: {msg}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(5)
        else:
            print("Todos los intentos fallaron")
            sys.exit(1)
