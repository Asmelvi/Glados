#!/usr/bin/env python3
import re, sys, json

def route(q: str) -> str:
    s = q.lower().strip()

    # 1) status codes (es/en) – ¡antes que títulos!
    status_pats = [
        r'\bc[oó]digos?\s*(de\s*)?(estado|http)\b',
        r'\bestados?\s*http\b',
        r'\bhttp\s*status\b',
        r'\bstatus\s*codes?\b',
    ]
    if any(re.search(p, s, re.I) for p in status_pats):
        return "web_status_codes"

    # 2) h1 texts
    h1_pats = [
        r'\b(h1|encabezad[oa]s?)\b',
        r'\bt[íi]tulo\s*principal\b',
        r'\bheaders?\s*h1\b',
    ]
    if any(re.search(p, s, re.I) for p in h1_pats):
        return "web_h1_texts"

    # 3) json api / apis
    api_pats = [
        r'\bjson\b',
        r'\bapi(s)?\b',
        r'\bendpoints?\b',
    ]
    if any(re.search(p, s, re.I) for p in api_pats):
        return "web_json_api"

    # 4) títulos por defecto
    title_pats = [
        r'\bt[íi]tulos?\b',
        r'\btitles?\b',
        r'\b<title>\b',
    ]
    if any(re.search(p, s, re.I) for p in title_pats):
        return "web_titles_hard"

    # fallback: si no reconoce, usa títulos (seguro)
    return "web_titles_hard"

if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else ""
    print(json.dumps({"skill": route(prompt)}, ensure_ascii=False))