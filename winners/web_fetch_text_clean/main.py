#!/usr/bin/env python3
import sys, os, csv, re, html
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
try:
    from readability import Document
    HAS_READABILITY = True
except Exception:
    HAS_READABILITY = False

def norm_one_line(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"\s+", " ", s, flags=re.MULTILINE).strip()
    return s

def strip_tags_regex(raw_html: str) -> str:
    txt = re.sub(r"(?is)<script.*?</script>", " ", raw_html)
    txt = re.sub(r"(?is)<style.*?</style>", " ", txt)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    return norm_one_line(txt)

def extract_text(html_bytes: bytes, url: str) -> str:
    text = ""
    if HAS_READABILITY:
        try:
            doc = Document(html_bytes, url=url)
            summary_html = doc.summary(html_partial=True)
            if summary_html:
                soup = BeautifulSoup(summary_html, "html.parser")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                text = norm_one_line(soup.get_text(separator=" "))
        except Exception:
            pass
    if not text:
        try:
            soup = BeautifulSoup(html_bytes, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            body = soup.body or soup
            text = norm_one_line(body.get_text(separator=" "))
        except Exception:
            pass
    if not text:
        try:
            soup = BeautifulSoup(html_bytes, "html.parser")
            title = soup.title.string if soup.title else ""
            text = norm_one_line(title or "")
        except Exception:
            text = ""
    return text

def main(task_dir: str) -> int:
    urls_path   = os.path.join(task_dir, "urls.txt")
    limit_path  = os.path.join(task_dir, "limit.txt")

    if not os.path.exists(urls_path):
        sys.stderr.write("missing urls.txt\n")
        return 2

    limit = None
    if os.path.exists(limit_path):
        try:
            limit = int(open(limit_path, "r", encoding="utf-8-sig", errors="ignore").read().strip().lstrip("\ufeff"))
            if limit <= 0: limit = None
        except Exception:
            limit = None

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; GladosFetcher/1.0; +https://example.invalid)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    })

    with open(urls_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        urls = [u.strip().lstrip("\ufeff") for u in f if u.strip()]

    writer = csv.writer(sys.stdout, lineterminator="\n")
    for raw in urls:
        url = raw.lstrip("\ufeff")
        text = ""
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            text = extract_text(resp.content, url)
            if not text:
                text = strip_tags_regex(resp.text)
        except Exception:
            text = ""
        if not text:
            sys.stderr.write(f"[warn] empty text for {url}\n")
        if limit is not None and text:
            if len(text) > limit:
                cut = text[:limit+10]
                m = re.search(r"^(.{0,"+str(limit)+r"})(?:\b|$)", cut)
                text = (m.group(1) if m else text[:limit]).rstrip()
        writer.writerow([url, text])
    return 0

if __name__ == "__main__":
    task_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    sys.exit(main(task_dir))