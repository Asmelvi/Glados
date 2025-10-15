import sys, asyncio, aiohttp
from bs4 import BeautifulSoup
from pathlib import Path

async def fetch(session, url):
    try:
        async with session.get(url, timeout=20) as r:
            html = await r.text(errors="ignore")
            return url, r.status, html
    except Exception:
        return url, None, ""

async def main(root):
    inp = Path(root)
    urls = []
    for p in sorted(inp.glob("*.txt")):
        urls += [u.strip() for u in p.read_text(encoding="utf-8", errors="ignore").splitlines() if u.strip()]
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[fetch(session, u) for u in urls])

    for url, status, html in results:
        text_links = []
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                t = (a.get_text(strip=True) or "").replace(",", " ")
                h = a["href"]
                text_links.append((t, h))
        if not text_links:
            print(f"{url},")
        else:
            for t,h in text_links:
                print(f"{url},{t} -> {h}")

if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv)>1 else "tasks/web_links/input"
    asyncio.run(main(root))