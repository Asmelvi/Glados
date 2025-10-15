#!/usr/bin/env python3
import sys, ssl, csv
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import build_opener, ProxyHandler, HTTPSHandler
from urllib.error import HTTPError, URLError

TARGET_META_NAMES = {
    "description", "og:title", "og:description", "og:image", "twitter:title",
    "twitter:description", "twitter:image"
}

class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []  # (key, value)
        self._in_head = False

    def handle_starttag(self, tag, attrs):
        a = dict((k.lower(), v) for k, v in attrs)
        tl = tag.lower()
        if tl == "head":
            self._in_head = True
        if tl == "meta":
            name = (a.get("name") or a.get("property") or "").strip()
            content = (a.get("content") or "").strip()
            if name and content:
                ln = name.lower()
                # guardamos solo targets (pero permitimos todos si quieres ampliar)
                if ln in TARGET_META_NAMES or ln.startswith("og:") or ln.startswith("twitter:"):
                    self.rows.append((name, content))
        if tl == "link":
            rel = (a.get("rel") or "").lower()
            href = (a.get("href") or "").strip()
            if href and ("icon" in rel or rel == "shortcut icon"):
                self.rows.append(("icon", href))

    def handle_endtag(self, tag):
        if tag.lower() == "head":
            self._in_head = False

def fetch(url: str, timeout: int = 15) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))
    opener.addheaders = [("User-Agent","Mozilla/5.0 (Glados/meta)")]
    try:
        with opener.open(url, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        try:
            return e.read().decode("utf-8", errors="replace")
        except:
            return ""
    except URLError:
        return ""
    except Exception:
        return ""

def main():
    if len(sys.argv) < 2:
        print("usage: main.py <input_dir>", file=sys.stderr)
        sys.exit(2)
    inp = Path(sys.argv[1])
    urls_file = inp / "urls.txt"
    if not urls_file.exists():
        print("missing urls.txt", file=sys.stderr)
        sys.exit(2)

    urls = []
    for line in urls_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.lstrip("\ufeff").strip()
        if line:
            urls.append(line)

    w = csv.writer(sys.stdout, lineterminator="\n")
    for base in urls:
        html = fetch(base)
        if not html:
            continue
        p = MetaParser()
        try:
            p.feed(html)
        except Exception:
            continue
        for key, val in p.rows:
            # normaliza a absoluto si parece URL
            if key.lower() in ("icon", "og:image", "twitter:image"):
                val = urljoin(base, val)
            w.writerow([base, key, val])

if __name__ == "__main__":
    main()