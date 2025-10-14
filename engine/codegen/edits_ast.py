# engine/codegen/edits_ast.py
"""
Recetas de mutación de código usando libcst (seguras y tolerantes).
Si una receta no encuentra su patrón, devuelve el código original.

Suposiciones mínimas del código semilla (plantilla CSV):
- Existe una variable 'p' con la ruta del directorio (str o Path).
- Se construye 'files' como lista de nombres de CSV a imprimir.
- main.py imprime líneas "nombre.csv,tamaño" al final.

Para la plantilla web (web_titles.py.j2):
- Existe un bloque marcado:
    # === BEGIN_FETCH_LOOP (mutation anchor) ===
    ...
    # === END_FETCH_LOOP ===
- La función fetch_one(url) existe.
- DEFAULT_HEADERS está definido.

Puedes añadir o quitar recetas en RECIPES. El entrypoint es ast_mutate(code, recipe).
"""

from __future__ import annotations
from typing import Optional
import re

import libcst as cst
import libcst.matchers as m


# ============================================================
# Utilidades comunes libcst
# ============================================================

def _ensure_import(module: cst.Module, import_stmt: str) -> cst.Module:
    """Inserta un import al principio si no existe ya (comprobación por texto)."""
    if import_stmt in module.code:
        return module
    return module.with_changes(
        body=[cst.parse_statement(import_stmt + "\n"), *module.body]
    )


def _try_parse(code: str) -> Optional[cst.Module]:
    try:
        return cst.parse_module(code)
    except Exception:
        return None


def _safe_transform(code: str, transformer: cst.CSTTransformer, *imports: str) -> str:
    mod = _try_parse(code)
    if not mod:
        return code
    try:
        mod2 = mod.visit(transformer)
        # Tras visitar, si la receta dijo "applied", añade imports necesarios
        if getattr(transformer, "applied", False):
            for imp in imports:
                mod2 = _ensure_import(mod2, imp)
        return mod2.code
    except Exception:
        return code


# ============================================================
# Receta: turbo_inline_print_flush
# ============================================================

class _FlushPrintTransform(cst.CSTTransformer):
    def __init__(self):
        self.applied = False

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        if m.matches(original_node.func, m.Name("print")):
            # Si ya tiene flush=..., no tocar
            for kw in original_node.keywords or []:
                if isinstance(kw.name, cst.Name) and kw.name.value == "flush":
                    return updated_node
            # Añade flush=True
            new_keywords = list(updated_node.keywords or [])
            new_keywords.append(cst.Arg(keyword=cst.Name("flush"), value=cst.Name("True")))
            self.applied = True
            return updated_node.with_changes(keywords=new_keywords)
        return updated_node


def recipe_turbo_inline_print_flush(code: str) -> str:
    return _safe_transform(code, _FlushPrintTransform())


# ============================================================
# Receta: add_lru_cache
# ============================================================

class _LRUCacheTransform(cst.CSTTransformer):
    def __init__(self):
        self.applied = False

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.FunctionDef:
        target_names = {"get_size", "stat_size", "size_of", "get_stat"}
        if original_node.name.value in target_names:
            # ya decorada?
            if any(m.matches(d, m.Decorator(decorator=m.Name("lru_cache"))) for d in original_node.decorators or []):
                return updated_node
            dec = cst.Decorator(decorator=cst.Call(
                func=cst.Name("lru_cache"),
                args=[cst.Arg(value=cst.Name("None"), keyword=cst.Name("maxsize"))]
            ))
            self.applied = True
            return updated_node.with_changes(decorators=[dec, *(updated_node.decorators or [])])
        return updated_node


def recipe_add_lru_cache(code: str) -> str:
    return _safe_transform(
        code,
        _LRUCacheTransform(),
        "from functools import lru_cache"
    )


# ============================================================
# Receta: use_scandir
# ============================================================

class _UseScandirTransform(cst.CSTTransformer):
    def __init__(self):
        self.applied = False

    def leave_SimpleStatementLine(self, node: cst.SimpleStatementLine,
                                  updated: cst.SimpleStatementLine) -> cst.BaseStatement:
        # Buscamos una asignación a "files = ..."
        if not node.body or not m.matches(node, m.SimpleStatementLine([m.Assign()])):
            return updated
        assign = node.body[0]
        if not m.matches(assign, m.Assign(targets=[m.AssignTarget(target=m.Name("files"))])):
            return updated

        new_code = r"""
paths = []
try:
    for de in os.scandir(p):
        if de.is_file() and de.name.endswith(".csv"):
            paths.append((de.name, de.path))
except Exception:
    from pathlib import Path as _P
    paths = [(f.name, str(f)) for f in _P(p).glob("*.csv")]

def _size(path):
    try:
        return os.stat(path).st_size
    except Exception:
        return -1

files = [name for (name, _path) in sorted(paths, key=lambda t: _size(t[1]), reverse=True)]
        """.strip()

        self.applied = True
        return cst.parse_statement(new_code)


def recipe_use_scandir(code: str) -> str:
    return _safe_transform(
        code,
        _UseScandirTransform(),
        "import os"
    )


# ============================================================
# Receta: threaded_stat
# ============================================================

class _ThreadedStatTransform(cst.CSTTransformer):
    def __init__(self):
        self.applied = False

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        return updated_node

    def leave_SimpleStatementLine(self, node: cst.SimpleStatementLine,
                                  updated: cst.SimpleStatementLine) -> cst.BaseStatement:
        if not node.body or not m.matches(node, m.SimpleStatementLine([m.Assign()])):
            return updated
        assign = node.body[0]
        if not m.matches(assign, m.Assign(targets=[m.AssignTarget(target=m.Name("files"))])):
            return updated

        new_code = r"""
paths = []
try:
    for de in os.scandir(p):
        if de.is_file() and de.name.endswith(".csv"):
            paths.append((de.name, de.path))
except Exception:
    from pathlib import Path as _P
    paths = [(f.name, str(f)) for f in _P(p).glob("*.csv")]

def _size(item):
    name, path = item
    try:
        return (name, os.stat(path).st_size)
    except Exception:
        return (name, -1)

with ThreadPoolExecutor() as ex:
    sized = list(ex.map(_size, paths))

files = [name for (name, _) in sorted(sized, key=lambda t: t[1], reverse=True)]
        """.strip()

        self.applied = True
        return cst.parse_statement(new_code)


def recipe_threaded_stat(code: str) -> str:
    return _safe_transform(
        code,
        _ThreadedStatTransform(),
        "from concurrent.futures import ThreadPoolExecutor",
        "import os"
    )


# ============================================================
# Receta: pandas_to_polars (no destructiva)
# ============================================================

class _PandasToPolarsTransform(cst.CSTTransformer):
    def __init__(self):
        self.applied = False

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        code = updated_node.code
        if "import pandas" not in code and "pd.read_" not in code and "pandas." not in code:
            return updated_node
        self.applied = True
        mod = _ensure_import(updated_node, "import polars as pl")
        return mod


def recipe_pandas_to_polars(code: str) -> str:
    return _safe_transform(code, _PandasToPolarsTransform())


# ============================================================
# Receta: multiprocessing_sizes
# ============================================================

class _MPTransform(cst.CSTTransformer):
    def __init__(self):
        self.applied = False

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        if not self.applied:
            return updated_node
        mod = updated_node
        mod = _ensure_import(mod, "from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor")
        mod = _ensure_import(mod, "import os")
        mod = _ensure_import(mod, "import sys")
        return mod

    def leave_SimpleStatementLine(self, node: cst.SimpleStatementLine,
                                  updated: cst.SimpleStatementLine) -> cst.BaseStatement:
        if not node.body or not m.matches(node, m.SimpleStatementLine([m.Assign()])):
            return updated
        assign = node.body[0]
        if not m.matches(assign, m.Assign(targets=[m.AssignTarget(target=m.Name("files"))])):
            return updated

        new_code = r"""
paths = []
try:
    for de in os.scandir(p):
        if de.is_file() and de.name.endswith(".csv"):
            paths.append((de.name, de.path))
except Exception:
    from pathlib import Path as _P
    paths = [(f.name, str(f)) for f in _P(p).glob("*.csv")]

def _size(path):
    try:
        return os.stat(path).st_size
    except Exception:
        return -1

# ProcessPool en Linux; ThreadPool en Windows
if sys.platform.startswith("win"):
    exec_cls = ThreadPoolExecutor
else:
    exec_cls = ProcessPoolExecutor

with exec_cls() as ex:
    sized = list(ex.map(lambda t: (t[0], _size(t[1])), paths))

files = [name for (name, _) in sorted(sized, key=lambda t: t[1], reverse=True)]
        """.strip()

        self.applied = True
        return cst.parse_statement(new_code)


def recipe_multiprocessing_sizes(code: str) -> str:
    return _safe_transform(code, _MPTransform())


# ============================================================
# Receta: async_glob
# ============================================================

class _AsyncGlobTransform(cst.CSTTransformer):
    def __init__(self):
        self.applied = False

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        if not self.applied:
            return updated_node
        mod = updated_node
        mod = _ensure_import(mod, "import asyncio")
        mod = _ensure_import(mod, "import os")
        return mod

    def leave_SimpleStatementLine(self, node: cst.SimpleStatementLine,
                                  updated: cst.SimpleStatementLine) -> cst.BaseStatement:
        if not node.body or not m.matches(node, m.SimpleStatementLine([m.Assign()])):
            return updated
        assign = node.body[0]
        if not m.matches(assign, m.Assign(targets=[m.AssignTarget(target=m.Name("files"))])):
            return updated

        new_code = r"""
async def _list_files_async(p):
    loop = asyncio.get_event_loop()
    def _scan():
        out = []
        for de in os.scandir(p):
            if de.is_file() and de.name.endswith(".csv"):
                try:
                    sz = os.stat(de.path).st_size
                except Exception:
                    sz = -1
                out.append((de.name, de.path, sz))
        return out
    return await loop.run_in_executor(None, _scan)

_sized = asyncio.run(_list_files_async(p))
_sized.sort(key=lambda t: t[2], reverse=True)
files = [name for (name, _path, _sz) in _sized]
        """.strip()

        self.applied = True
        return cst.parse_statement(new_code)


def recipe_async_glob(code: str) -> str:
    return _safe_transform(code, _AsyncGlobTransform())


# ============================================================
# Utilidades de reemplazo por marcadores (para plantilla WEB)
# ============================================================

def _replace_block_between(mark_start: str, mark_end: str, new_block: str, src: str) -> str:
    """
    Reemplaza el contenido entre comentarios:
        # === {mark_start} ===
            ...
        # === {mark_end} ===
    Mantiene las líneas con los marcadores.
    """
    pattern = re.compile(
        rf"(?s)(\s*#\s*===\s*{re.escape(mark_start)}\s*===.*?\n)(.*?)(\s*#\s*===\s*{re.escape(mark_end)}\s*===.*?\n)"
    )
    def repl(m):
        return f"{m.group(1)}{new_block}\n{m.group(3)}"
    return re.sub(pattern, repl, src, count=1)


# ============================================================
# Recetas WEB: threaded_fetch / add_retry_headers / disk_cache
# Requieren que la plantilla tenga los anchors BEGIN_FETCH_LOOP / END_FETCH_LOOP.
# ============================================================

def recipe_threaded_fetch(code: str) -> str:
    """
    Paraleliza el bucle de descargas usando ThreadPoolExecutor
    **preservando el orden de entrada** con ex.map(fetch_one, urls).
    """
    block = """
    from concurrent.futures import ThreadPoolExecutor
    workers = min(8, max(1, len(urls)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for url, title in ex.map(fetch_one, urls):
            print(f"{url},{title}")
    """.rstrip()

    # Soporta marcadores con y sin “(mutation anchor)”
    out = _replace_block_between("BEGIN_FETCH_LOOP (mutation anchor)", "END_FETCH_LOOP", block, code)
    if out == code:
        out = _replace_block_between("BEGIN_FETCH_LOOP", "END_FETCH_LOOP", block, code)
    return out


def recipe_add_retry_headers(code: str) -> str:
    """
    Inserta sesión requests con retries y usa esa sesión en fetch_one().
    Conserva DEFAULT_HEADERS.
    """
    # imports
    if "from requests.adapters import HTTPAdapter" not in code:
        code = code.replace("import requests", "import requests\nfrom requests.adapters import HTTPAdapter", 1)
    if "from urllib3.util.retry import Retry" not in code:
        code = code.replace("from requests.adapters import HTTPAdapter",
                            "from requests.adapters import HTTPAdapter\nfrom urllib3.util.retry import Retry", 1)

    # _build_session
    if "_build_session()" not in code:
        ins = """
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
"""
        code = code.replace(
            "def fetch_one(url: str, *, timeout: float = 10.0) -> tuple[str, str]:",
            ins + "\n" + "def fetch_one(url: str, *, timeout: float = 10.0) -> tuple[str, str]:",
            1
        )

    # _SESSION sentinel
    if "_SESSION = None" not in code:
        code = code.replace("DEFAULT_HEADERS = {", "_SESSION = None\n\nDEFAULT_HEADERS = {", 1)

    # parchear fetch_one a usar _SESSION
    code = re.sub(
        r"def fetch_one\(url: str, \*, timeout: float = 10\.0\) -> tuple\[str, str\]:\s*\n\s*try:\s*\n\s*"
        r"r = requests\.get\(url, headers=DEFAULT_HEADERS, timeout=timeout\)\s*\n\s*"
        r"r\.raise_for_status\(\)\s*\n\s*return url, extract_title\(r\.text\)\s*\n\s*except Exception:\s*\n\s*"
        r"return url, \"\".*?\n",
        (
            "def fetch_one(url: str, *, timeout: float = 10.0) -> tuple[str, str]:\n"
            "    global _SESSION\n"
            "    try:\n"
            "        if _SESSION is None:\n"
            "            _SESSION = _build_session()\n"
            "        r = _SESSION.get(url, timeout=timeout)\n"
            "        r.raise_for_status()\n"
            "        return url, extract_title(r.text)\n"
            "    except Exception:\n"
            "        return url, \"\"\n"
        ),
        code,
        count=1,
        flags=re.DOTALL
    )
    return code


def recipe_disk_cache(code: str) -> str:
    """
    Añade caché en disco .cache_web/<sha1(url)>.html dentro de fetch_one().
    """
    # imports auxiliares
    if "import hashlib" not in code:
        code = code.replace("import sys, re", "import sys, re, hashlib, os", 1)

    # helper _cache_path_for
    if "_cache_path_for(" not in code:
        helper = """
def _cache_path_for(url: str) -> Path:
    root = Path(".cache_web")
    root.mkdir(exist_ok=True)
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return root / f"{h}.html"
"""
        code = code.replace(
            "def fetch_one(url: str, *, timeout: float = 10.0) -> tuple[str, str]:",
            helper + "\n" + "def fetch_one(url: str, *, timeout: float = 10.0) -> tuple[str, str]:",
            1
        )

    # parchear fetch_one con cache
    code = re.sub(
        r"def fetch_one\(url: str, \*, timeout: float = 10\.0\) -> tuple\[str, str\]:\s*\n\s*try:\s*\n\s*"
        r"(.*?)\n\s*except Exception:\s*\n\s*return url, \"\"",
        (
            "def fetch_one(url: str, *, timeout: float = 10.0) -> tuple[str, str]:\n"
            "    try:\n"
            "        cp = _cache_path_for(url)\n"
            "        if cp.exists():\n"
            "            html = cp.read_text(encoding=\"utf-8\", errors=\"ignore\")\n"
            "            return url, extract_title(html)\n"
            "        sess = globals().get('_SESSION', None)\n"
            "        if sess is not None:\n"
            "            r = sess.get(url, timeout=timeout)\n"
            "        else:\n"
            "            r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)\n"
            "        r.raise_for_status()\n"
            "        html = r.text\n"
            "        try:\n"
            "            cp.write_text(html, encoding=\"utf-8\")\n"
            "        except Exception:\n"
            "            pass\n"
            "        return url, extract_title(html)\n"
            "    except Exception:\n"
            "        return url, \"\"\n"
        ),
        code,
        count=1,
        flags=re.DOTALL
    )
    return code


# ============================================================
# Registro de recetas y entrypoint
# ============================================================

RECIPES = [
    "pandas_to_polars",
    "add_lru_cache",
    "turbo_inline_print_flush",
    "use_scandir",
    "threaded_stat",
    "multiprocessing_sizes",
    "async_glob",

    # WEB
    "threaded_fetch",
    "add_retry_headers",
    "disk_cache",
    "aiohttp_fetch",
]
# ============================================================
# Receta WEB: aiohttp_fetch (asyncio + aiohttp)
# Reemplaza el bucle de fetch por una versión asíncrona concurrente
# usando un ClientSession compartido y un pool de conexiones.
# ============================================================

def recipe_aiohttp_fetch(code: str) -> str:
    block = r"""
    import asyncio, aiohttp

    async def _run_async(urls):
        timeout = aiohttp.ClientTimeout(total=10)
        # limit controla el máximo de sockets simultáneos
        connector = aiohttp.TCPConnector(limit=16, ssl=False)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers=DEFAULT_HEADERS) as sess:

            async def one(u: str):
                try:
                    async with sess.get(u) as resp:
                        resp.raise_for_status()
                        html = await resp.text()
                        return u, extract_title(html)
                except Exception:
                    return u, ""

            tasks = [asyncio.create_task(one(u)) for u in urls]
            for coro in asyncio.as_completed(tasks):
                url, title = await coro
                print(f"{url},{title}")

    asyncio.run(_run_async(urls))
    """.rstrip()

    # Soporta ambos formatos de ancla:
    patched = _replace_block_between("BEGIN_FETCH_LOOP (mutation anchor)", "END_FETCH_LOOP", block, code)
    if patched == code or not patched:
        patched = _replace_block_between("BEGIN_FETCH_LOOP", "END_FETCH_LOOP", block, code)
    return patched or code


def ast_mutate(code: str, recipe: str) -> str:
    """
    Devuelve el código mutado por la receta dada (o el original si no aplica).
    """
    try:
        if recipe == "pandas_to_polars":
            return recipe_pandas_to_polars(code)
        if recipe == "add_lru_cache":
            return recipe_add_lru_cache(code)
        if recipe == "turbo_inline_print_flush":
            return recipe_turbo_inline_print_flush(code)
        if recipe == "use_scandir":
            return recipe_use_scandir(code)
        if recipe == "threaded_stat":
            return recipe_threaded_stat(code)
        if recipe == "multiprocessing_sizes":
            return recipe_multiprocessing_sizes(code)
        if recipe == "async_glob":
            return recipe_async_glob(code)

        # WEB
        if recipe == "threaded_fetch":
            return recipe_threaded_fetch(code)
        if recipe == "add_retry_headers":
            return recipe_add_retry_headers(code)
        if recipe == "disk_cache":
            return recipe_disk_cache(code)

    except Exception:
        # Si cualquier receta falla por excepción, devolver original
        return code
    return code
