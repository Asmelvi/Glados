import sys, re
from pathlib import Path
from html.parser import HTMLParser
from html import unescape

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._buf = []
        self._skip = 0  # para <script> y <style>

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ("script", "style") and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0 and data:
            self._buf.append(data)

    def text(self):
        raw = unescape(" ".join(self._buf))
        # normaliza todo el espacio a una sola línea
        return re.sub(r"\s+", " ", raw).strip()

def main():
    if len(sys.argv) < 2:
        print("usage: main.py <input_dir>", file=sys.stderr)
        sys.exit(2)

    inp = Path(sys.argv[1])
    html_path = inp / "html.txt"
    if not html_path.exists():
        print("missing input/html.txt", file=sys.stderr)
        sys.exit(2)

    html = html_path.read_text(encoding="utf-8", errors="ignore")
    parser = TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        # si hay HTML roto, aún así intentamos imprimir lo recolectado
        pass

    print(parser.text())
    sys.exit(0)

if __name__ == "__main__":
    main()