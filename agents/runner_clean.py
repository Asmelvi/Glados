import sys, os, re, csv, json, datetime, subprocess, pathlib
from urllib.parse import urlparse

try:
    from agents.prefs import domain_limit
except Exception:
    def domain_limit(domain: str, default_limit):
        return default_limit

ROOT = pathlib.Path(__file__).resolve().parent.parent

def _ts():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def _extract(prompt: str):
    urls = re.findall(r'(https?://[^\s,;]+)', prompt, flags=re.I)
    m    = re.search(r'(\d+)\s*caracter', prompt, flags=re.I)
    limit = int(m.group(1)) if m else None
    return urls, limit

def _write_inputs(task_dir: pathlib.Path, urls, _global_limit_ignored):
    """Escribimos siempre limit.txt vacío para que la skill NO recorte.
    El recorte se hará en post-proceso por dominio."""
    inp = task_dir / "input"
    inp.mkdir(parents=True, exist_ok=True)
    (inp / "urls.txt").write_text("\n".join(urls) + "\n", encoding="utf-8")
    (inp / "limit.txt").write_text("", encoding="utf-8")
    return inp

def _ensure_results_from_stdout(skill_dir: pathlib.Path):
    results = skill_dir / "results.csv"
    if results.exists():
        return results
    stdout_log = skill_dir / "logs" / "stdout.txt"
    if not stdout_log.exists():
        return results
    lines = stdout_log.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return results
    first = lines[0].strip().lower()
    if first.startswith("url,title,h1,meta_description,texto"):
        results.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif first.startswith("url,texto"):
        out = ["url,title,h1,meta_description,texto"]
        for ln in lines[1:]:
            if not ln.strip():
                continue
            url, rest = (ln.split(",", 1) + [""])[:2]
            out.append(f"{url},,,,{rest}")
        results.write_text("\n".join(out) + "\n", encoding="utf-8")
    else:
        out = ["url,title,h1,meta_description,texto"] + lines
        results.write_text("\n".join(out) + "\n", encoding="utf-8")
    return results

def _postprocess_domain_limits(results_csv: pathlib.Path, global_limit: int|None):
    if not results_csv.exists():
        return
    rows = []
    with results_csv.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        fieldnames = rdr.fieldnames or []
        fieldnames = ["url","title","h1","meta_description","texto"]
        for r in rdr:
            url = (r.get("url") or "").strip()
            dom = urlparse(url).netloc.lower().lstrip("www.")
            eff = domain_limit(dom, global_limit)
            texto = r.get("texto") or ""
            if eff and eff > 0:
                texto = texto[:eff]
            rows.append({
                "url": r.get("url",""),
                "title": r.get("title",""),
                "h1": r.get("h1",""),
                "meta_description": r.get("meta_description",""),
                "texto": texto,
            })
    with results_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["url","title","h1","meta_description","texto"])
        w.writeheader()
        w.writerows(rows)

def run_clean_direct(prompt: str):
    urls, limit = _extract(prompt)
    if not urls:
        return {"ok": False, "learned": ["(nota) No se detectaron URLs."], "skill_dir": None}

    orders   = ROOT / "workspace" / "orders"
    orders.mkdir(parents=True, exist_ok=True)
    order_root = orders / _ts()
    skill_dir  = order_root / "web_fetch_text_clean"
    (skill_dir / "logs").mkdir(parents=True, exist_ok=True)

    inp = _write_inputs(skill_dir, urls, limit)

    entry = ROOT / "winners" / "web_fetch_text_clean" / "main.py"
    cmd   = [sys.executable, str(entry), str(inp)]

    stdout_log = skill_dir / "logs" / "stdout.txt"
    stderr_log = skill_dir / "logs" / "stderr.txt"
    with stdout_log.open("w", encoding="utf-8", newline="") as out, \
         stderr_log.open("w", encoding="utf-8", newline="") as err:
        subprocess.run(cmd, cwd=str(ROOT), stdout=out, stderr=err, check=False)

    results = _ensure_results_from_stdout(skill_dir)
    _postprocess_domain_limits(results, limit)

    head = []
    try:
        with results.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                head.append(line.rstrip("\n"))
                if i >= 2:
                    break
    except Exception as e:
        head = [f"(nota) No pude leer resultados: {e}"]

    learned = [f"He generado un CSV con texto limpio. Muestra (fuente: {results.name}):"] + head
    return {"ok": True, "learned": learned, "skill_dir": str(skill_dir)}