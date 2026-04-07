from pathlib import Path
import pandas as pd, json

BASE = Path(__file__).resolve().parents[1]
RAW  = BASE / "data" / "datasets" / "raw"
OUTR = BASE / "data" / "personality_questions.json"                 # runtime used by API
OUTP = BASE / "data" / "datasets" / "processed" / "ipip_items.json" # processed copy
OUTP.parent.mkdir(parents=True, exist_ok=True)

# find the Excel key
cands = list(RAW.glob("*ItemKey*.xls*")) or list(RAW.glob("*.xls*"))
if not cands:
    raise SystemExit(f"No Excel key found in {RAW}. Put IPIP-NEO-ItemKey.xls/.xlsx there.")
XLS = cands[0]
engine = "xlrd" if XLS.suffix.lower() == ".xls" else "openpyxl"

# trait mapping helper
TRAIT_MAP = {
    "OPENNESS":"O","O":"O",
    "CONSCIENTIOUSNESS":"C","C":"C",
    "EXTRAVERSION":"E","E":"E",
    "AGREEABLENESS":"A","A":"A",
    "NEUROTICISM":"N","EMOTIONAL STABILITY":"N","N":"N",
}

def map_trait(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    # try direct name/letter first
    up = s.upper()
    if up in TRAIT_MAP:
        return TRAIT_MAP[up]
    # sometimes "Key" column holds full names like "Agreeableness"
    for k,v in TRAIT_MAP.items():
        if up == k:
            return v
    # sometimes "Facet" like "E1 Warmth" -> take first letter
    if s and s[0].upper() in "OCEAN":
        return s[0].upper()
    return None

def is_reverse_from_sign(val):
    if pd.isna(val):
        return False
    s = str(val).strip()
    # typical in this key: '+' normal, '-' reverse
    return s == "-" or s.lower() in {"rev","r","reverse","reversed","neg","negative","1","true","t","yes","y"}

LIKERT = [
    {"id":"a","label":"Strongly disagree","score":1},
    {"id":"b","label":"Disagree","score":2},
    {"id":"c","label":"Neutral","score":3},
    {"id":"d","label":"Agree","score":4},
    {"id":"e","label":"Strongly agree","score":5},
]

# read all sheets; your header preview was from the first sheet
xl = pd.ExcelFile(XLS, engine=engine)
questions, qid = [], 1
for sheet in xl.sheet_names:
    df = xl.parse(sheet)
    cols = {c.lower(): c for c in df.columns}

    # expect these exact names from your file
    item_col  = cols.get("item")     # question text
    key_col   = cols.get("key")      # domain name or letter (if available)
    facet_col = cols.get("facet")    # e.g., E1, A2 -> first letter is domain
    sign_col  = cols.get("sign")     # '+' or '-'

    if not item_col:
        continue  # not a data sheet

    for _, r in df.iterrows():
        text = str(r.get(item_col, "")).strip()
        if not text:
            continue

        # derive trait
        trait = None
        if key_col is not None:
            trait = map_trait(r.get(key_col))
        if not trait and facet_col is not None:
            trait = map_trait(r.get(facet_col))
        if trait not in {"O","C","E","A","N"}:
            continue

        # reverse?
        rev = is_reverse_from_sign(r.get(sign_col)) if sign_col is not None else False

        questions.append({"id": qid, "text": text, "trait": trait, "reverse": rev})
        qid += 1

if not questions:
    raise SystemExit("Parsed 0 questions. Double-check column names are exactly: Item, Key, Facet, Sign.")

bundle = {"traits":["O","C","E","A","N"], "likert": LIKERT, "questions": questions}
OUTR.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
OUTP.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"✓ Wrote {len(questions)} questions")
print(f"  Runtime:   {OUTR}")
print(f"  Processed: {OUTP}")
