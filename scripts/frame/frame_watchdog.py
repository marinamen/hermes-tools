#!/usr/bin/env python3
"""
Samsung The Frame — watchdog: si la tele está en standby, Wake-on-LAN +
modo arte con la última imagen del carrusel. Cada 5 min.

Wake the TV from standby and restore Art Mode:
- PowerState vacío "" ahora se trata como "on" (la API responde, así que
  la tele está despierta — el campo viene vacío en algunos firmwares).
- Solo despierta si PowerState == 'standby' o la API no responde.
"""
import sys, os, time, socket, requests

sys.path.insert(0, '/Users/sitamendieta/Library/Python/3.9/lib/python/site-packages')

import signal
def _timeout_handler(signum, frame):
    print("⏱️  Timeout — TV no responde a tiempo")
    raise SystemExit(1)
signal.signal(signal.SIGALRM, _timeout_handler)
signal.alarm(45)  # 45s hard limit


TV_IP = os.getenv('FRAME_TV_IP', '192.168.0.26')
TV_PORT = 8001
TV_MAC = os.getenv('FRAME_TV_MAC', 'AA:BB:CC:DD:EE:FF')
BASE = os.path.expanduser('~/Gits/frame-control')
TOKEN_FILE = os.path.join(BASE, 'state', 'samsung_token2.txt')
LAST_IMAGE_FILE = os.path.join(BASE, 'state', 'frame_last_image.txt')
DEFAULT_IMAGE = 'MY_F0322'


def get_power_state():
    try:
        r = requests.get(f'http://{TV_IP}:{TV_PORT}/api/v2/', timeout=5)
        return r.json().get('device', {}).get('PowerState', '')
    except Exception:
        return 'offline'


def get_last_image():
    try:
        v = open(LAST_IMAGE_FILE).read().strip()
        return v or DEFAULT_IMAGE
    except Exception:
        return DEFAULT_IMAGE


def wake_on_lan():
    mac_bytes = bytes.fromhex(TV_MAC.replace(':', ''))
    magic = b'\xff' * 6 + mac_bytes * 16
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(magic, ('255.255.255.255', 9))
    sock.close()


def ensure_art_mode(target_image=None):
    from samsungtvws.art import SamsungTVArt
    art = SamsungTVArt(TV_IP, port=TV_PORT, token_file=TOKEN_FILE, timeout=30)
    try:
        art.open()
        mode = art.get_artmode()
        if mode != 'on':
            art.set_artmode('on')
            time.sleep(2)
        if target_image:
            art.select_image(target_image, show=True)
        art.close()
        return True
    except Exception as e:
        print(f"❌ Error art mode: {str(e)[:120]}")
        try: art.close()
        except Exception: pass
        return False


state = get_power_state()
# Estado vacío "" pero API responde → tele despierta (firmware quirk)
effective = 'on' if state in ('on', '') else state
print(f"[{time.strftime('%Y-%m-%d %H:%M')}] PowerState={state!r} efectivo={effective}")

if effective == 'standby':
    print("Standby → enviando Wake-on-LAN")
    wake_on_lan()
    time.sleep(10)
    ensure_art_mode(get_last_image())
elif effective == 'on':
    # Solo asegurar modo arte si lleva tiempo en otro modo — chequeo ligero
    from samsungtvws.art import SamsungTVArt
    try:
        art = SamsungTVArt(TV_IP, port=TV_PORT, token_file=TOKEN_FILE, timeout=15)
        art.open()
        mode = art.get_artmode()
        print(f"Art mode: {mode}")
        if mode != 'on':
            print("Reactivando modo arte")
            art.set_artmode('on')
            time.sleep(2)
            art.select_image(get_last_image(), show=True)
        art.close()
    except Exception as e:
        print(f"❌ Check: {str(e)[:120]}")
        sys.exit(1)
else:
    # offline real
    print(f"⚠️  Tele offline ({effective})")
    sys.exit(1)
