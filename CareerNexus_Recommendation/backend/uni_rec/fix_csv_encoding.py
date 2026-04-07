# fix_csv_encoding.py
from __future__ import annotations
import os, sys, shutil, time
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
EXTS = {".csv"}

def detect_encoding(raw: bytes) -> str:
    """
    Very safe heuristic detector.
    Tries utf-8/utf-8-sig first; falls back to Windows-1252 then latin-1.
    """
    for enc in ("utf-8", "utf-8-sig"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            pass
    # Common Windows encodings:
    for enc in ("cp1252", "latin-1"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    # If truly unknown, decode with replacement using latin-1 to be safe
    return "latin-1"

def to_utf8(path: Path) -> tuple[bool, str, str]:
    """
    Convert file at `path` to UTF-8 (no BOM). Returns (changed?, from_enc, to_enc).
    Makes a timestamped .bak backup before writing.
    """
    raw = path.read_bytes()
    enc = detect_encoding(raw)

    # If already clean utf-8 without BOM, skip.
    try:
        raw.decode("utf-8")
        already_utf8 = True
    except UnicodeDecodeError:
        already_utf8 = False

    # If utf-8-sig, we still re-save to strip BOM.
    if already_utf8 and enc != "utf-8-sig":
        return (False, enc, "utf-8")

    text = raw.decode(enc, errors="replace")

    # Backup once per run (timestamped, so it never overwrites)
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".{ts}.bak")
    shutil.copy2(path, bak)

    # Write normalized UTF-8 with LF line endings
    # (newline='' lets Python normalize to \n; pandas handles fine)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)

    return (True, enc, "utf-8")

def main():
    if not DATA_DIR.exists():
        print(f"❌ data folder not found: {DATA_DIR}")
        sys.exit(1)

    # Safety: ask user to close Excel if open
    print("🔒 Make sure Excel/Editors are CLOSED for files in:", DATA_DIR)
    changed = 0
    total = 0
    print("\n🔍 Scanning CSVs…\n")

    for p in sorted(DATA_DIR.iterdir()):
        if p.suffix.lower() not in EXTS or not p.is_file():
            continue
        total += 1
        try:
            did, frm, to = to_utf8(p)
            if did:
                changed += 1
                print(f"✅ {p.name}: {frm} → {to}  (backup saved as .bak)")
            else:
                print(f"⏭  {p.name}: already UTF-8")
        except Exception as e:
            print(f"⚠️  {p.name}: failed to convert ({e})")

    print("\n— Summary —")
    print(f"Total CSVs: {total}")
    print(f"Converted : {changed}")
    print(f"Unchanged : {total - changed}")
    print("\nDone ✔")

if __name__ == "__main__":
    main()
