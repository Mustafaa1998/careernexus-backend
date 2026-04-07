import re
from typing import Iterable, List

STOP = {"and","or","for","to","with","in","of","the","a","an","on","at","by","from"}

def normalize_terms(items: Iterable[str]) -> List[str]:
    out = []
    for it in items:
        s = re.sub(r"[^a-z0-9+# ]+"," ", str(it).lower()).strip()
        toks = [t for t in s.split() if t and t not in STOP]
        out.extend(toks)
    seen=set(); uniq=[]
    for t in out:
        if t in seen: continue
        seen.add(t); uniq.append(t)
    return uniq
