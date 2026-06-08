#!/usr/bin/env python3
"""
Reestructura a YYYY/YYYY-MM-Mes/ (sin nivel día) y convierte JPG/TIF → HEIC.
"""
import subprocess, shutil, json
from pathlib import Path
from datetime import datetime

DST = Path("os.path.expanduser("~/Pictures/Photo-Archive")")
LOG = DST / "_log.txt"
ERR = DST / "_errores.txt"

MESES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
         7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

CONVERT_EXTS = {".jpg", ".jpeg", ".tif", ".tiff"}
KEEP_EXTS = {".raw",".cr2",".nef",".arw",".dng",".orf",".rw2",
             ".mp4",".mov",".m4v",".3gp",".mts",".avi",".mkv",".heic",".heif"}
QUALITY = 80

def log(m):
    line = f"[{datetime.now():%F %T}] {m}"
    print(line, flush=True)
    with open(LOG,"a") as f: f.write(line+"\n")

def err(m):
    with open(ERR,"a") as f: f.write(f"[{datetime.now():%F %T}] {m}\n")

def get_date(p):
    """EXIF DateTimeOriginal > CreateDate > FileModifyDate > mtime"""
    try:
        out = subprocess.run(
            ["exiftool","-j","-q","-DateTimeOriginal","-CreateDate","-FileModifyDate", str(p)],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(out.stdout) if out.stdout.strip() else []
        if data:
            for k in ("DateTimeOriginal","CreateDate","FileModifyDate"):
                v = data[0].get(k)
                if not v: continue
                v = str(v).split("+")[0].split("Z")[0].strip()
                try:
                    dt = datetime.strptime(v[:19], "%Y:%m:%d %H:%M:%S")
                    if 1990 <= dt.year <= 2030: return dt
                except ValueError: pass
    except Exception as e: err(f"exif {p}: {e}")
    try: return datetime.fromtimestamp(p.stat().st_mtime)
    except: return datetime(2000,1,1)

def safe_name(parent, name):
    target = parent / name
    if not target.exists(): return target
    stem, suf = target.stem, target.suffix
    i = 1
    while True:
        c = parent.with_name  # noop
        c = parent / f"{stem}_{i}{suf}"
        if not c.exists(): return c
        i += 1

def convert_to_heic(src, dst_heic):
    """heif-enc preserva EXIF por defecto."""
    r = subprocess.run(
        ["heif-enc","-q",str(QUALITY),"-o",str(dst_heic), str(src)],
        capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        raise RuntimeError(f"heif-enc fail: {r.stderr.strip()[:200]}")
    if not dst_heic.exists() or dst_heic.stat().st_size < 1000:
        raise RuntimeError("output too small or missing")
    return dst_heic.stat().st_size

# ============ Recolectar ============
log("=== Recolectando archivos ===")
files = [p for p in DST.rglob("*") if p.is_file() and not p.name.startswith("_") and not p.name.startswith(".")]
log(f"Total: {len(files)}")

before_size = sum(p.stat().st_size for p in files)
log(f"Tamaño antes: {before_size/1e9:.2f} GB")

# ============ Procesar ============
moved = converted = saved_bytes = skipped = failed = 0
for p in files:
    ext = p.suffix.lower()
    dt = get_date(p)
    new_dir = DST / f"{dt.year}" / f"{dt.year}-{dt.month:02d}-{MESES[dt.month]}"
    new_dir.mkdir(parents=True, exist_ok=True)

    if ext in CONVERT_EXTS:
        new_name = p.stem + ".heic"
        target = new_dir / new_name
        if target.exists(): target = safe_name(new_dir, new_name)
        try:
            orig_size = p.stat().st_size
            new_size = convert_to_heic(p, target)
            converted += 1
            saved_bytes += (orig_size - new_size)
            p.unlink()
        except Exception as e:
            err(f"convert {p}: {e}"); failed += 1
            if target.exists():
                try: target.unlink()
                except: pass
    elif ext in KEEP_EXTS:
        target = new_dir / p.name
        if target == p: skipped += 1; continue
        if target.exists(): target = safe_name(new_dir, p.name)
        try:
            shutil.move(str(p), str(target)); moved += 1
        except Exception as e:
            err(f"move {p}: {e}"); failed += 1
    else:
        err(f"unknown ext: {p}"); failed += 1

# Limpieza de carpetas vacías (días viejos)
for d in sorted(DST.rglob("*"), key=lambda x: -len(str(x))):
    if d.is_dir():
        try:
            if not any(d.iterdir()): d.rmdir()
        except: pass

# ============ Resumen ============
after_files = [p for p in DST.rglob("*") if p.is_file() and not p.name.startswith("_") and not p.name.startswith(".")]
after_size = sum(p.stat().st_size for p in after_files)
log(f"=== FIN: convertidos={converted}, movidos={moved}, sin-cambio={skipped}, fallos={failed}")
log(f"Antes: {before_size/1e9:.2f} GB → Después: {after_size/1e9:.2f} GB (ahorro: {(before_size-after_size)/1e9:.2f} GB, {100*(before_size-after_size)/before_size:.1f}%)")

subprocess.run(["osascript","-e",
    f'display notification "{converted} HEIC, {len(after_files)} total, {after_size/1e9:.1f} GB (ahorro {(before_size-after_size)/1e9:.1f} GB)" with title "Reorganización completa"'])
