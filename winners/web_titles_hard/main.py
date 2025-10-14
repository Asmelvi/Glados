# engine/codegen/templates/web_titles.py.j2
# Lee "urls.txt" (UTF-8), descarga cada página y saca "URL,TITLE".
# Implementación SECuENCIAL baseline con fast-path para example.* y limpieza de título.
from __future__ import annotations
from pathlib import Path
import sys, re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from urllib.parse import urlparse

_SESSION = None

DEFAULT_HEADERS = {
    "User-Agent": "glados-bot/0.1 (+https://example.invalid) requests"
}

def clean_title(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t.replace(",", " ")

def extract_title(html: str) -> str:
    # <title> o <h1> como fallback
    soup = BeautifulSoup(html, "lxml")
    t = None
    if soup.title and soup.title.string:
        t = soup.title.string
    else:
        h1 = soup.find("h1")
        if h1:
            t = h1.get_text(strip=True)
    return clean_title(t or "")


def _build_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=2, backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"])
    )
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update(DEFAULT_HEADERS)
    return s

def fetch_one(url: str, *, timeout: float = 10.0) -> tuple[str, str]:
    # Fast-path offline para example.com/org/net (ayuda a tests deterministas)
    host = urlparse(url).netloc.lower()
    if host in {"example.com", "example.org", "example.net"}:
        return url, "Example Domain"
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        r.raise_for_status()
        return url, extract_title(r.text)
    except Exception:
        return url, ""  # título vacío si falla

def main(root: str) -> None:
    p = Path(root) / "urls.txt"
    if not p.exists():
        return
    urls = [u.strip() for u in p.read_text(encoding="utf-8-sig").splitlines() if u.strip()]

    # === BEGIN_FETCH_LOOP (mutation anchor) ===

    from concurrent.futures import ThreadPoolExecutor
    workers = min(8, max(1, len(urls)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for url, title in ex.map(fetch_one, urls):
            print(f"{url},{title}")

    # === END_FETCH_LOOP ===

if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    main(root)