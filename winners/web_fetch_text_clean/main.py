# -*- coding: utf-8 -*-
import sys, pathlib, re, csv, textwrap
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[2]  # winners/<skill>/ -> repo root
def read_file(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def read_urls(task_dir: pathlib.Path):
    p = task_dir / "urls.txt"
    raw = p.read_bytes()
    # tolera BOM
    txt = raw.decode("utf-8-sig", errors="replace")
    urls = []
    for line in txt.splitlines():
        line = line.strip()
        if not line: continue
        urls.append(line)
    return urls

def read_limit(task_dir: pathlib.Path) -> int | None:
    p = task_dir / "limit.txt"
    if not p.exists(): return None
    s = read_file(p).strip()
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None

def fetch(url: str, timeout=20):
    hdrs = {
        "User-Agent": "Mozilla/5.0 (compatible; GladosBot/1.0; +https://example.local)"
    }
    r = requests.get(url, headers=hdrs, timeout=timeout)
    r.raise_for_status()
    return r.text

def clean_text(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # Extraer meta
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    h1_el = soup.find("h1")
    h1 = h1_el.get_text(" ", strip=True) if h1_el else ""
    meta_desc = ""
    m = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if m and m.get("content"):
        meta_desc = m["content"].strip()

    # Limpiar texto principal visible
    for tag in soup(["script","style","noscript","template"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()

    return title, h1, meta_desc, text

def main():
    if len(sys.argv) < 2:
        print("Uso: main.py <task_dir>", file=sys.stderr)
        sys.exit(2)
    task_dir = pathlib.Path(sys.argv[1])

    urls = read_urls(task_dir)
    limit = read_limit(task_dir)

    out = sys.stdout
    w = csv.writer(out, lineterminator="\n")
    # Cabecera completa
    w.writerow(["url","title","h1","meta_description","texto"])

    for url in urls:
        try:
            html = fetch(url)
            title, h1, meta_desc, text = clean_text(html)
            trimmed = text[:limit] if limit else text
            w.writerow([url, title, h1, meta_desc, trimmed])
        except Exception as e:
            # fila con error, deja campos vacíos excepto url y texto=mensaje
            w.writerow([url, "", "", "", f"(error) {e}"])

if __name__ == "__main__":
    main()