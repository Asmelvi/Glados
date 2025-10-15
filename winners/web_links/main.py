import sys, ssl, csv
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser

class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_a = False
        self._cur_href = None
        self._buf = []
        self.anchors = []  # list[(text, href)]

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._in_a = True
            self._cur_href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._in_a:
            text = "".join(self._buf).strip()
            href = (self._cur_href or "").strip()
            if href:
                self.anchors.append((text, href))
            self._in_a = False
            self._cur_href = None
            self._buf.clear()

    def handle_data(self, data):
        if self._in_a and data:
            self._buf.append(data)

def fetch(url: str, timeout: int = 15) -> str:
    # TLS laxo (permite sitios con cert roto)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # Fuerza SIN proxy dentro del contenedor
    opener = build_opener(
        ProxyHandler({}),               # no proxies
        HTTPSHandler(context=ctx),
    )
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (Glados/links)")]
    try:
        with opener.open(url, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        try:
            return e.read().decode("utf-8", errors="replace")
        except Exception:
            return ""
    except URLError as e:
        sys.stderr.write(f"[warn] URLError {url}: {e}\\n")
        return ""
    except Exception as e:
        sys.stderr.write(f"[warn] fetch error {url}: {e}\\n")
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

    w = csv.writer(sys.stdout, lineterminator="\\n")
    for base in urls:
        html = fetch(base)
        if not html:
            sys.stderr.write(f"[info] empty body: {base}\\n")
            continue
        p = AnchorParser()
        try:
            p.feed(html)
        except Exception as e:
            sys.stderr.write(f"[warn] parse error {base}: {e}\\n")
            continue
        if not p.anchors:
            sys.stderr.write(f"[info] no anchors found: {base}\\n")
        for text, href in p.anchors:
            abs_href = urljoin(base, href)
            w.writerow([base, text, abs_href])

if __name__ == "__main__":
    main()