# app/mongo_utils.py
from __future__ import annotations
from typing import Dict, Any, List

def _flatten(prefix: str, data: Dict[str, Any], out: Dict[str, Any]) -> None:
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            _flatten(key, v, out)
        else:
            out[key] = v

def build_set_update(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert nested dict into dot-notation paths for Mongo $set.
    Example:
      {"name":"A", "resume":{"skills":["Py"]}}
    -> {"$set":{"name":"A","resume.skills":["Py"]}}
    """
    flat: Dict[str, Any] = {}
    _flatten("", payload, flat)
    if not flat:
        return {}
    return {"$set": flat}
