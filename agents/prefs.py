import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _merge(base, override):
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override or base
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out

# Defaults versionados
cfg_defaults = _load(ROOT / "config" / "prefs.json")
# Overrides locales (opcional)
ws_overrides = _load(ROOT / "workspace" / "prefs.json")
PREFS = _merge(cfg_defaults, ws_overrides)

def domain_limit(domain: str, global_limit: int | None) -> int | None:
    """
    Devuelve el límite efectivo para un dominio:
      - Si hay override en PREFS, usa ese valor.
      - Si no, usa global_limit (puede ser None).
    """
    domain = (domain or "").lower().lstrip(".")
    d = PREFS.get("domain_overrides", {})
    if domain in d and isinstance(d[domain], dict) and "limit" in d[domain]:
        return int(d[domain]["limit"])
    return global_limit