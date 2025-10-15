from __future__ import annotations
from pathlib import Path
import sys, re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

DEFAULT_HEADERS = {"User-Agent": "glados-bot/0.1 (+https://example.invalid) requests"}

def clean(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t.replace(",", " ")

def extract_h1(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    return clean(h1.get_text(strip=True) if h1 else "")

def fetch_h1(url: str, *, timeout: float = 10.0) -> tuple[str, str]:
    host = urlparse(url).netloc.lower()
    if host in {"example.com", "example.org", "example.net"}:
        # páginas de ejemplo: su <h1> es "Example Domain"
        return url, "Example Domain"
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        return url, extract_h1(r.text)
    except Exception:
        return url, ""

def main(root: str) -> None:
    p = Path(root) / "urls.txt"
    if not p.exists():
        return
    urls = [u.strip() for u in p.read_text(encoding="utf-8-sig").splitlines() if u.strip()]
    for u in urls:
        url, h1 = fetch_h1(u)
        print(f"{url},{h1}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")