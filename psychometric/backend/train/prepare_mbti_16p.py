# backend/train/prepare_mbti_16p.py
from pathlib import Path
import json
import pandas as pd
import numpy as np

BASE = Path(__file__).resolve().parents[1]
RAW = BASE / "data" / "datasets" / "raw"
OUT = BASE / "data" / "datasets" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

# We will auto-pick one of these files if present (Excel preferred)
CANDIDATES = ["16P.xlsx", "16P.xls", "16P.csv"]

OUT_CSV = OUT / "mbti_16p_processed.csv"
META = BASE / "models" / "mbti_meta.json"
META.parent.mkdir(parents=True, exist_ok=True)

def find_input():
    # try exact names first
    for name in CANDIDATES:
        p = RAW / name
        if p.exists():
            return p
    # else, fallback to any 16P.* file
    for p in sorted(RAW.glob("16P.*")):
        if p.suffix.lower() in {".xlsx", ".xls", ".csv"}:
            return p
    raise SystemExit(f"No 16P dataset found in {RAW}. Put 16P.xlsx / 16P.xls / 16P.csv there.")

def load_any(path: Path) -> pd.DataFrame:
    suf = path.suffix.lower()
    if suf == ".csv":
        # Try UTF-8 first, then Windows encodings, and auto-detect delimiter
        # newline='' avoids extra \r characters on Windows
        try:
            return pd.read_csv(path, sep=None, engine="python")  # sniff delimiter
        except UnicodeDecodeError:
            for enc in ("cp1252", "latin1", "iso-8859-1"):
                try:
                    return pd.read_csv(path, sep=None, engine="python", encoding=enc)
                except UnicodeDecodeError:
                    continue
            # last resort: ignore bad bytes
            return pd.read_csv(path, sep=None, engine="python", encoding="utf-8", errors="ignore")
    elif suf in {".xlsx", ".xls"}:
        try:
            return pd.read_excel(path)  # first sheet
        except Exception:
            engine = "xlrd" if suf == ".xls" else "openpyxl"
            return pd.read_excel(path, engine=engine)
    else:
        raise SystemExit(f"Unsupported file type: {path.suffix}")

def main():
    INPUT = find_input()
    print(f"→ Using dataset: {INPUT}")
    df = load_any(INPUT)

    # try to find the label column
    candidates = ["Personality", "personality", "Type", "type", "MBTI", "mbti"]
    label_col = next((c for c in df.columns if str(c).strip() in candidates), None)
    if not label_col:
        # try case-insensitive exact match
        lower_map = {str(c).strip().lower(): c for c in df.columns}
        for key in ["personality", "type", "mbti"]:
            if key in lower_map:
                label_col = lower_map[key]
                break
    if not label_col:
        raise SystemExit(f"Could not find label column (expected Personality/Type/MBTI). Found: {list(df.columns)[:10]} ...")

    # keep only numeric columns as features (drop label + any non-numeric)
    feature_cols = [c for c in df.columns if c != label_col and pd.api.types.is_numeric_dtype(df[c])]
    if not feature_cols:
        # try forcing numeric conversion on everything except label
        tmp = df.drop(columns=[label_col]).apply(pd.to_numeric, errors="coerce")
        feature_cols = [c for c in tmp.columns if pd.api.types.is_numeric_dtype(tmp[c])]
        df[tmp.columns] = tmp
    if not feature_cols:
        raise SystemExit("No numeric feature columns found. Inspect your sheet; answers must be numeric (e.g., -3..+3).")

    X = df[feature_cols].copy()
    y = df[label_col].astype(str).str.strip()

    # clean numeric: replace inf/nan, clip to a typical 16P range
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    X = X.clip(lower=-3, upper=3)

    processed = pd.concat([X, y.rename("Personality")], axis=1)
    processed.to_csv(OUT_CSV, index=False)

    meta = {
        "source_file": str(INPUT.name),
        "feature_names": feature_cols,        # IMPORTANT: order to keep for inference
        "label_name": "Personality",
        "input_range_hint": [-3, 3],
        "n_items": len(feature_cols)
    }
    META.write_text(json.dumps(meta, indent=2))

    print(f"✓ Wrote {OUT_CSV}  (rows={len(processed)}, features={len(feature_cols)})")
    print(f"✓ Wrote meta: {META}")

if __name__ == "__main__":
    main()
