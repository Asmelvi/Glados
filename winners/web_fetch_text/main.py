import sys, ssl, re, csv
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import build_opener, ProxyHandler, HTTPSHandler
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser
import html as ihtml

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_ign = 0  # depth inside script/style/noscript
        self._buf = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t in ("script", "style", "noscript"):
            self._in_ign += 1

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ("script", "style", "noscript") and self._in_ign > 0:
            self._in_ign -= 1

    def handle_data(self, data):
        if self._in_ign or not data:
            return
        self._buf.append(data)

    def handle_comment(self, data):
        # ignorar comentarios
        pass

    def text(self):
        raw = "".join(self._buf)
        # unescape entidades HTML
        raw = ihtml.unescape(raw)
        # normalizar espacios y saltos
        raw = re.sub(r'\s+', ' ', raw).strip()
        return raw

def fetch(url: str, timeout: int = 20) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    opener = build_opener(
        ProxyHandler({}),         # sin proxy dentro de docker
        HTTPSHandler(context=ctx)
    )
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (Glados/web_fetch_text)")]

    try:
        with opener.open(url, timeout=timeout) as r:
            # intenta usar charset de cabeceras; si no, decodifica en utf-8 tolerante
            data = r.read()
            ct = r.headers.get("Content-Type", "")
            m = re.search(r"charset=([\w\-]+)", ct, flags=re.I)
            enc = m.group(1) if m else "utf-8"
            try:
                return data.decode(enc, errors="replace")
            except Exception:
                return data.decode("utf-8", errors="replace")
    except HTTPError as e:
        try:
            return e.read().decode("utf-8", errors="replace")
        except Exception:
            return ""
    except URLError as e:
        sys.stderr.write(f"[warn] URLError {url}: {e}\n")
        return ""
    except Exception as e:
        sys.stderr.write(f"[warn] fetch error {url}: {e}\n")
        return ""

def html_to_text(html: str) -> str:
    p = TextExtractor()
    try:
        p.feed(html)
    except Exception:
        # si el parser falla a mitad, usa lo que haya
        pass
    return p.text()

def main():
    if len(sys.argv) < 2:
        print("usage: main.py <input_dir>", file=sys.stderr)
        sys.exit(2)

    inp = Path(sys.argv[1])
    urls_file = inp / "urls.txt"
    if not urls_file.exists():
        print("missing urls.txt", file=sys.stderr)
        sys.exit(2)

    # Leer URLs (quitando posible BOM y líneas vacías)
    urls = []
    for line in urls_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.lstrip("\ufeff").strip()
        if line:
            urls.append(line)

    w = csv.writer(sys.stdout, lineterminator="\n")
    for base in urls:
        html = fetch(base)
        if not html:
            sys.stderr.write(f"[info] empty body: {base}\n")
            w.writerow([base, ""])
            continue
        txt = html_to_text(html)
        w.writerow([base, txt])

if __name__ == "__main__":
    main()