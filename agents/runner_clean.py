# -*- coding: utf-8 -*-
import pathlib, datetime, re, subprocess, sys, json, os

ROOT = pathlib.Path(__file__).resolve().parent.parent

def _ts():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def _extract(prompt: str):
    # URLs
    urls = re.findall(r'(https?://[^\s,;]+)', prompt, flags=re.I)
    # Límite: "a 300 caracteres", "a 400", etc.
    m = re.search(r'a\s*(\d+)\s*caracter', prompt, flags=re.I)
    limit = int(m.group(1)) if m else None
    return urls, limit

def run_clean_direct(prompt: str):
    """
    Ejecuta winners/web_fetch_text_clean/main.py directamente.
    Devuelve: {"rc": int, "results_csv": str, "stdout_log": str, "workdir": str}
    """
    urls, limit = _extract(prompt)
    orders = ROOT / "workspace" / "orders"
    orders.mkdir(parents=True, exist_ok=True)
    order_root = orders / _ts()
    skill_dir  = order_root / "web_fetch_text_clean"
    inp        = skill_dir / "input"
    logs       = skill_dir / "logs"
    for d in (inp, logs): d.mkdir(parents=True, exist_ok=True)

    # inputs
    (inp / "urls.txt").write_text("\n".join(urls) + "\n", encoding="utf-8")
    if limit is not None:
        (inp / "limit.txt").write_text(str(limit), encoding="utf-8")

    # ejecutar main.py
    entry = ROOT / "winners" / "web_fetch_text_clean" / "main.py"
    cmd   = [sys.executable, str(entry), str(inp)]
    try:
        out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="replace")
        (logs / "stdout.txt").write_text(out, encoding="utf-8")
        results_csv = skill_dir / "results.csv"
        results_csv.write_text(out, encoding="utf-8")
        # Asegurar cabecera 5 columnas
        first = out.splitlines()[0] if out else ""
        if first.strip() != "url,title,h1,meta_description,texto":
            # Forzar re-ejecución sin depender de stdout previo (debería ser ya 5 col, pero por si acaso)
            out2 = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="replace")
            results_csv.write_text(out2, encoding="utf-8")
        return {"rc": 0, "results_csv": str(results_csv), "stdout_log": str(logs / "stdout.txt"), "workdir": str(skill_dir)}
    except subprocess.CalledProcessError as e:
        (logs / "stderr.txt").write_text(str(e), encoding="utf-8")
        return {"rc": e.returncode, "results_csv": "", "stdout_log": str(logs / "stderr.txt"), "workdir": str(skill_dir)}