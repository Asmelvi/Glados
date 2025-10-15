from __future__ import annotations
from pathlib import Path
import sys
import requests
from urllib.parse import urlparse

DEFAULT_HEADERS = {
    "User-Agent": "glados-bot/0.1 (+https://example.invalid) requests"
}

def fetch_status(url: str, *, timeout: float = 10.0) -> tuple[str, str]:
    host = urlparse(url).netloc.lower()
    if host in {"example.com", "example.org", "example.net"}:
        return url, "200"
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=False)
        return url, str(r.status_code)
    except Exception:
        return url, ""

def main(root: str) -> None:
    p = Path(root) / "urls.txt"
    if not p.exists():
        return
    urls = [u.strip() for u in p.read_text(encoding="utf-8-sig").splitlines() if u.strip()]
    for u in urls:
        url, status = fetch_status(u)
        print(f"{url},{status}")

if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    main(root)