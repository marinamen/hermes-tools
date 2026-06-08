#!/usr/bin/env python3
"""Selecciona un año aleatorio (2002-2015), 40 fotos con caras, fit + fecha,
sube al Frame y reemplaza el carrusel activo.
Ejecutado por cron Hermes a las 10h, 14h, 18h (3×/día)."""
import cv2, json, time, warnings, subprocess, random, gc, re, sys
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw, ImageFont
from datetime import datetime
warnings.filterwarnings('ignore')

YEARS_POOL = list(range(2002, 2016))
TARGET = 40
ROOT_BASE = Path("/Users/sitamendieta/Pictures/Fotos Disco Duro")
LOG = Path("/Users/sitamendieta/Gits/frame-control/logs/refresh_random.log")
WORK = Path("/tmp/frame_refresh"); WORK.mkdir(exist_ok=True)
MESES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
         7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
FONT_FILE = "/System/Library/Fonts/Helvetica.ttc"

def log(m):
    line = f"[{datetime.now():%F %T}] {m}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG,"a") as f: f.write(line+"\n")

# Elegir año al azar (preferentemente que tenga muchas fotos)
candidates = [(y, len(list((ROOT_BASE/str(y)).rglob("*.JPG")) + list((ROOT_BASE/str(y)).rglob("*.jpg"))))
              for y in YEARS_POOL]
candidates = [(y,n) for y,n in candidates if n >= 50]
log(f"Años disponibles con >=50 fotos: {[(y,n) for y,n in candidates]}")
year = random.choice([y for y,_ in candidates])
log(f"=== AÑO ELEGIDO: {year} ===")

ROOT = ROOT_BASE / str(year)
cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

photos = [p for p in ROOT.rglob("*") if p.is_file() and p.suffix.lower() in {".jpg",".jpeg"}
          and p.stat().st_size > 100_000]
log(f"Fotos {year}: {len(photos)}")

# Si hay > 1500, muestreamos para acelerar
if len(photos) > 1500:
    random.shuffle(photos)
    photos = photos[:1500]
    log(f"  muestreado a 1500 para velocidad")

with_faces = []
for p in photos:
    try:
        img = cv2.imread(str(p))
        if img is None: continue
        h, w = img.shape[:2]
        if max(h,w) > 1000:
            s = 1000/max(h,w)
            img2 = cv2.resize(img, (int(w*s), int(h*s)))
        else: img2 = img
        gray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=6, minSize=(50,50))
        if len(faces) >= 1: with_faces.append((p, len(faces)))
        del img, img2, gray; gc.collect()
    except: pass
log(f"Con caras: {len(with_faces)}")

if not with_faces:
    log("Sin fotos con caras, abort"); sys.exit(1)

by_month = {}
for p, n in with_faces:
    m = p.parts[-2]
    by_month.setdefault(m,[]).append((p,n))
months = sorted(by_month.keys())
random.seed()  # aleatorio cada ejecución
per_month = max(1, TARGET // max(1, len(months)))
selected = []
for m in months:
    pool = sorted(by_month[m], key=lambda x:-x[1])[:per_month*3]
    random.shuffle(pool)
    selected.extend([p for p,_ in pool[:per_month]])
if len(selected) < TARGET:
    rest = [p for p,_ in sorted(with_faces, key=lambda x:-x[1]) if p not in selected]
    random.shuffle(rest)
    selected.extend(rest[:TARGET - len(selected)])
random.shuffle(selected)
selected = selected[:TARGET]
log(f"Seleccionadas: {len(selected)}")

def label_from_path(p):
    parent = p.parts[-2]
    m = re.match(r"(\d{4})-(\d{2})-(.+)", parent)
    if m:
        yr, mm, mes = m.groups()
        return f"{mes} {yr}"
    dt = datetime.fromtimestamp(p.stat().st_mtime)
    return f"{MESES[dt.month]} {dt.year}"

def prep(src, idx):
    try:
        img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        w, h = img.size
        portrait = h > w
        tw, th = (2160,3840) if portrait else (3840,2160)
        scale = min(tw/w, th/h)
        nw, nh = int(w*scale), int(h*scale)
        img = img.resize((nw, nh), Image.LANCZOS)
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=100, threshold=3))
        img = ImageEnhance.Contrast(img).enhance(1.08)
        img = ImageEnhance.Color(img).enhance(1.10)
        final = Image.new("RGB", (tw,th), (0,0,0))
        final.paste(img, ((tw-nw)//2, (th-nh)//2))
        draw = ImageDraw.Draw(final)
        label = label_from_path(src)
        size = 64 if portrait else 80
        try: font = ImageFont.truetype(FONT_FILE, size)
        except: font = ImageFont.load_default()
        bbox = draw.textbbox((0,0), label, font=font)
        tw_t = bbox[2]-bbox[0]; th_t = bbox[3]-bbox[1]
        x = tw - tw_t - 60; y = th - th_t - 80
        for dx,dy in [(-2,0),(2,0),(0,-2),(0,2),(-2,-2),(2,2),(-2,2),(2,-2)]:
            draw.text((x+dx,y+dy), label, font=font, fill=(0,0,0))
        draw.text((x,y), label, font=font, fill=(255,255,255))
        out = WORK / f"rf_{idx:02d}.jpg"
        final.save(out, "JPEG", quality=92, subsampling=0)
        return out
    except Exception as e:
        log(f"prep fail {src.name}: {e}"); return None

prepared = []
for i, p in enumerate(selected, 1):
    o = prep(p, i)
    if o: prepared.append(o)
    gc.collect()
log(f"Preparadas: {len(prepared)}")

from samsungtvws.art import SamsungTVArt
TOKEN = "/Users/sitamendieta/Gits/frame-control/state/samsung_token2.txt"
art = SamsungTVArt(os.getenv('FRAME_TV_IP', '192.168.0.26'), port=8001, token_file=TOKEN, timeout=15)
new_ids = []
for i, p in enumerate(prepared, 1):
    try:
        with open(p,'rb') as f: data = f.read()
        r = art.upload(data, file_type='JPEG', matte='none', portrait_matte='none')
        new_ids.append(r)
        if i % 10 == 0 or i == len(prepared): log(f"  subidas {i}/{len(prepared)}")
        time.sleep(2)
    except Exception as e:
        log(f"upload fail: {e}")
        try: art = SamsungTVArt(os.getenv('FRAME_TV_IP', '192.168.0.26'), port=8001, token_file=TOKEN, timeout=15)
        except: pass

if new_ids:
    active = Path("/Users/sitamendieta/Gits/frame-control/scripts/frame_carousel_active.json")
    active.write_text(json.dumps(new_ids))
    Path("/Users/sitamendieta/Gits/frame-control/state/frame_carousel_index.txt").write_text("0")
    log(f"=== Carrusel reemplazado: {len(new_ids)} fotos de {year} ===")
    try:
        art.select_image(new_ids[0], show=True)
        log(f"Mostrando: {new_ids[0]}")
    except Exception as e:
        log(f"select fail: {e}")
else:
    log("NO se subió nada, carrusel sin cambios")
