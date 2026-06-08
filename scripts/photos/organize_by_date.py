#!/usr/bin/env python3
"""
Filtra y reorganiza SOLO fotos/vídeos de cámara real desde Transcend.

CRITERIO FOTO REAL:
  - Tiene EXIF Make o Model (cámara/móvil), O
  - Es RAW (cr2/nef/arw/dng/orf/rw2/raw)
  - Y NO es screenshot/captura por nombre
  - Y tamaño >= 200 KB
  - Y resolución >= 1024x768 (si se puede leer)
  - GIF, PNG sin EXIF, WebP, BMP → fuera

CRITERIO VÍDEO REAL:
  - mp4/mov/m4v/3gp/mts/avi/mkv
  - Tamaño >= 1 MB
  - Tiene metadata cámara (Make/Model) O duración >= 3s (si se puede leer)
  - No tiene "screen"/"recording" en el nombre

ESTRUCTURA: YYYY/YYYY-MM-Mes/YYYY-MM-DD/archivo.ext
FECHA: EXIF DateTimeOriginal > CreateDate > mtime
"""
import os, sys, shutil, subprocess, json, re
from datetime import datetime
from pathlib import Path

DST = Path("os.path.expanduser("~/Pictures/Photo-Archive")")
SRC = Path("os.environ.get("SOURCE_DIR", "/Volumes/Source")")
LOG = DST / "_log.txt"
ERR = DST / "_errores.txt"
REJECTED_LOG = DST / "_rechazados.txt"

MESES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
         7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

PHOTO_EXTS = {".jpg",".jpeg",".heic",".heif",".tif",".tiff",
              ".raw",".cr2",".nef",".arw",".dng",".orf",".rw2"}
VIDEO_EXTS = {".mp4",".mov",".m4v",".3gp",".mts",".avi",".mkv"}
RAW_EXTS = {".raw",".cr2",".nef",".arw",".dng",".orf",".rw2"}
JUNK_EXTS = {".gif",".png",".webp",".bmp",".svg",".ico"}  # se descartan SIEMPRE

MIN_PHOTO_BYTES = 200_000
MIN_VIDEO_BYTES = 1_000_000
MIN_PIXELS = 1024 * 768

SCREEN_RE = re.compile(r"(screenshot|screen[\s_-]*shot|captura|screen[\s_-]*recording|grab)", re.I)

def log(msg):
    line = f"[{datetime.now():%F %T}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def err(msg):
    with open(ERR, "a") as f: f.write(f"[{datetime.now():%F %T}] {msg}\n")

def rej(p, reason):
    with open(REJECTED_LOG, "a") as f: f.write(f"{reason}\t{p}\n")

def get_metadata(files):
    """exiftool batch → dict path -> {Make, Model, DateTimeOriginal/CreateDate/FileModifyDate, ImageWidth, ImageHeight, Duration}"""
    if not files: return {}
    result = {}
    for i in range(0, len(files), 300):
        batch = files[i:i+300]
        try:
            out = subprocess.run(
                ["exiftool","-j","-q","-Make","-Model","-DateTimeOriginal","-CreateDate",
                 "-FileModifyDate","-ImageWidth","-ImageHeight","-Duration","-MediaDuration"]
                 + [str(p) for p in batch],
                capture_output=True, text=True, timeout=600
            )
            data = json.loads(out.stdout) if out.stdout.strip() else []
            for entry in data:
                src = entry.get("SourceFile")
                if src: result[src] = entry
        except Exception as e:
            err(f"exiftool batch fallo: {e}")
    return result

def parse_date(entry, fallback_mtime):
    for key in ("DateTimeOriginal","CreateDate","FileModifyDate"):
        val = entry.get(key) if entry else None
        if not val: continue
        val = str(val).split("+")[0].split("Z")[0].strip()
        try:
            dt = datetime.strptime(val[:19], "%Y:%m:%d %H:%M:%S")
            if 1990 <= dt.year <= 2030: return dt
        except ValueError: pass
    return fallback_mtime

def is_real_photo(p, entry):
    ext = p.suffix.lower()
    if ext in JUNK_EXTS: return False, "junk-ext"
    if ext not in PHOTO_EXTS: return False, "not-photo-ext"
    if SCREEN_RE.search(p.name): return False, "screenshot-name"
    try:
        size = p.stat().st_size
    except: return False, "stat-fail"
    if size < MIN_PHOTO_BYTES and ext not in RAW_EXTS: return False, f"too-small-{size}"
    if ext in RAW_EXTS: return True, "raw"
    has_camera = bool(entry and (entry.get("Make") or entry.get("Model")))
    if not has_camera: return False, "no-exif-camera"
    w, h = entry.get("ImageWidth"), entry.get("ImageHeight")
    if w and h and (int(w) * int(h)) < MIN_PIXELS:
        return False, f"low-res-{w}x{h}"
    return True, "ok"

def is_real_video(p, entry):
    ext = p.suffix.lower()
    if ext not in VIDEO_EXTS: return False, "not-video-ext"
    if SCREEN_RE.search(p.name): return False, "screenrec-name"
    try:
        size = p.stat().st_size
    except: return False, "stat-fail"
    if size < MIN_VIDEO_BYTES: return False, f"too-small-{size}"
    has_camera = bool(entry and (entry.get("Make") or entry.get("Model")))
    if has_camera: return True, "camera"
    dur = entry.get("Duration") or entry.get("MediaDuration") if entry else None
    if dur:
        try:
            s = str(dur)
            if ":" in s:
                parts = [float(x) for x in s.split(":")]
                secs = parts[0]*3600 + parts[1]*60 + parts[2] if len(parts)==3 else parts[0]*60+parts[1]
            else: secs = float(s)
            if secs >= 3: return True, f"dur-{secs:.1f}s"
        except: pass
    if size >= 10_000_000: return True, "large-no-meta"
    return False, "no-camera-meta"

def dest_path(dt, filename):
    return DST / f"{dt.year}" / f"{dt.year}-{dt.month:02d}-{MESES[dt.month]}" / f"{dt.year}-{dt.month:02d}-{dt.day:02d}" / filename

def safe_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        try:
            if dst.stat().st_size == src.stat().st_size: return "dup"
        except: pass
        stem, suf = dst.stem, dst.suffix
        i = 1
        while True:
            cand = dst.with_name(f"{stem}_{i}{suf}")
            if not cand.exists(): dst = cand; break
            i += 1
    shutil.copy2(str(src), str(dst))
    return "ok"

def collect(root):
    out = []
    if not root.exists(): return out
    for p in root.rglob("*"):
        if not p.is_file(): continue
        sp = str(p)
        if "$RECYCLE.BIN" in sp or "System Volume Information" in sp: continue
        if p.name.startswith("_") or p.name == ".DS_Store" or p.name.startswith("."): continue
        out.append(p)
    return out

# ============ PASO 0: borrar lo basura ya copiado ============
log("=== PASO 0: limpiar destino de archivos no-foto ya copiados ===")
existing = collect(DST)
log(f"Total en destino antes: {len(existing)}")
# Pasa exiftool sobre los existentes para clasificar
ex_meta = get_metadata(existing)
removed = 0
for p in existing:
    ext = p.suffix.lower()
    if ext in JUNK_EXTS:
        try: p.unlink(); removed += 1
        except: pass
        continue
    entry = ex_meta.get(str(p), {})
    if ext in PHOTO_EXTS:
        ok, reason = is_real_photo(p, entry)
    elif ext in VIDEO_EXTS:
        ok, reason = is_real_video(p, entry)
    else:
        ok, reason = False, "unknown-ext"
    if not ok:
        rej(p, f"limpieza:{reason}")
        try: p.unlink(); removed += 1
        except: pass

# Limpia .DS_Store
for ds in DST.rglob(".DS_Store"):
    try: ds.unlink()
    except: pass

# Limpia carpetas vacías
for d in sorted(DST.rglob("*"), key=lambda x: -len(str(x))):
    if d.is_dir():
        try:
            if not any(d.iterdir()): d.rmdir()
        except: pass

log(f"PASO 0 fin: eliminados={removed}, quedan={sum(1 for p in DST.rglob('*') if p.is_file() and not p.name.startswith('_'))}")

# ============ PASO 1: leer Transcend, filtrar, copiar ============
log("=== PASO 1: scan Transcend ===")
if not SRC.exists():
    log("Transcend NO montado, abort"); sys.exit(1)

src_files = collect(SRC)
log(f"Archivos candidatos en Transcend: {len(src_files)}")

# Pre-filtro rápido por extensión y tamaño para no llamar exiftool sobre basura obvia
prefiltered = []
for p in src_files:
    ext = p.suffix.lower()
    if ext in JUNK_EXTS:
        rej(p, "ext-junk"); continue
    if ext not in PHOTO_EXTS and ext not in VIDEO_EXTS:
        rej(p, "ext-other"); continue
    try: size = p.stat().st_size
    except: rej(p, "stat-fail"); continue
    if ext in PHOTO_EXTS and ext not in RAW_EXTS and size < MIN_PHOTO_BYTES:
        rej(p, f"prefilter-photo-small-{size}"); continue
    if ext in VIDEO_EXTS and size < MIN_VIDEO_BYTES:
        rej(p, f"prefilter-video-small-{size}"); continue
    if SCREEN_RE.search(p.name):
        rej(p, "name-screen"); continue
    prefiltered.append(p)

log(f"Tras pre-filtro: {len(prefiltered)} candidatos a leer EXIF")

meta = get_metadata(prefiltered)
log(f"Metadata leída: {len(meta)}/{len(prefiltered)}")

# Set de lo ya presente (nombre, tamaño)
present = set()
for p in DST.rglob("*"):
    if p.is_file() and not p.name.startswith("_"):
        try: present.add((p.name, p.stat().st_size))
        except: pass

copied = dup = rejected = failed = 0
for p in prefiltered:
    entry = meta.get(str(p), {})
    ext = p.suffix.lower()
    if ext in PHOTO_EXTS:
        ok, reason = is_real_photo(p, entry)
    else:
        ok, reason = is_real_video(p, entry)
    if not ok:
        rej(p, f"exif:{reason}"); rejected += 1; continue
    try:
        sz = p.stat().st_size
    except:
        failed += 1; continue
    if (p.name, sz) in present:
        dup += 1; continue
    try: mt = datetime.fromtimestamp(p.stat().st_mtime)
    except: mt = datetime(2000,1,1)
    dt = parse_date(entry, mt)
    target = dest_path(dt, p.name)
    try:
        r = safe_copy(p, target)
        if r == "dup": dup += 1
        else: copied += 1
    except Exception as e:
        err(f"copiar {p}: {e}"); failed += 1

log(f"PASO 1 fin: copiados={copied}, dup={dup}, rechazados-por-exif={rejected}, fallos={failed}")

# ============ RESUMEN ============
total = sum(1 for p in DST.rglob("*") if p.is_file() and not p.name.startswith("_"))
years = sorted({p.name for p in DST.iterdir() if p.is_dir() and p.name.isdigit()})
size = subprocess.run(["du","-sh",str(DST)], capture_output=True, text=True).stdout.split()[0]
yr_range = f"{years[0]}–{years[-1]}" if years else "sin años"
log(f"=== FIN: {total} archivos en {len(years)} años ({yr_range}), {size} ===")
subprocess.run(["osascript","-e",
    f'display notification "{total} fotos en {len(years)} años, {size}" with title "Transcend filtrado y archivado"'])
