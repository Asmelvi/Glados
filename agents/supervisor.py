# -*- coding: utf-8 -*-
import argparse, os, sys, subprocess, datetime, json, re, pathlib
from agents.runner_clean import run_clean_direct

# Memoria / diario
try:
    from agents.memory import log_event, add_goal
except Exception:
    def log_event(event_type, message, meta=None): pass
    def add_goal(goal_text): pass

ROOT = pathlib.Path(__file__).resolve().parent.parent

def router_skill(prompt: str) -> str:
    """Pregunta al router oficial cuál skill usar; fallback si falla."""
    try:
        cmd = [sys.executable, str(ROOT / "tools" / "router.py"), prompt]
        out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="replace")
        data = json.loads(out.strip())
        return data.get("skill") or "web_titles_hard"
    except Exception:
        return "web_titles_hard"

def write_chat(session_root: pathlib.Path, role: str, text: str) -> None:
    session_root.mkdir(parents=True, exist_ok=True)
    path = session_root / "chat.txt"
    ts   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {role}: {text}\n")

def run_order(prompt: str) -> dict:
    """Llama al orquestador (order.ps1). Devuelve {rc, stdout, stderr} o raw."""
    try:
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "order.ps1"), prompt, "-Yes"]
        out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="replace")
        m = re.search(r'^\{.*\}', out, re.MULTILINE)
        if m:
            return json.loads(m.group(0))
        return {"rc": -1, "stdout": "", "stderr": "", "raw": out}
    except subprocess.CalledProcessError as e:
        return {"rc": e.returncode, "stdout": "", "stderr": str(e), "raw": getattr(e, "output", "")}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", help="Instrucción en lenguaje natural")
    parser.add_argument("--approve", "-y", action="store_true", help="Ejecutar plan con aprobación")
    args = parser.parse_args()

    prompt = args.prompt

    # Sesión y registro
    sessions_dir = ROOT / "workspace" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_root = sessions_dir / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    session_root.mkdir(parents=True, exist_ok=True)

    # Plan
    skill = router_skill(prompt)
    plan_lines = [
        f"=== PLAN PROPUESTO ===",
        f"Skill sugerida: {skill}",
        "Acciones:",
        "  1) Extraer URLs del prompt.",
        "  2) Preparar inputs efímeros (order.ps1 ya lo hace).",
        "  3) Ejecutar en sandbox con límites.",
        "  4) Guardar resultados y hacer resumen corto."
    ]
    urls = re.findall(r'(https?://[^\s,;]+)', prompt, flags=re.I)
    if urls:
        plan_lines.append(f"URLs detectadas: {', '.join(urls)}")
    log_event("plan", "Propuesta de plan generado por supervisor.", {"skill": skill, "urls": urls})
    write_chat(session_root, "supervisor", "Propuesta de plan:\n" + "\n".join(plan_lines))
    print("\n".join(plan_lines))
    if not args.approve:
        print("Plan listo. Para ejecutar añade --approve (o -y).")
        return

    # Ejecución aprobada
    log_event("run", "Supervisor ejecuta plan (aprobado)", {"skill": skill})
    write_chat(session_root, "supervisor", "Ejecutando plan con aprobación…")

    res = run_clean_direct(prompt) if skill == "web_fetch_text_clean" else run_order(prompt)
    learned = []

    # Vista previa: preferir results.csv (5 columnas) y si no, logs/stdout.txt
    try:
        orders_dir = ROOT / "workspace" / "orders"
        last_order = max([p for p in orders_dir.iterdir() if p.is_dir()],
                         key=lambda p: p.stat().st_mtime, default=None)
        if last_order:
            skill_dir  = max([p for p in last_order.iterdir() if p.is_dir()],
                             key=lambda p: p.stat().st_mtime, default=None)
            if skill_dir:
                stdout_log = skill_dir / "logs" / "stdout.txt"
                results    = skill_dir / "results.csv"
                head = []
                src  = None
                if results.exists():
                    src = results
                elif stdout_log.exists():
                    src = stdout_log
                if src:
                    with open(src, "r", encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f):
                            head.append(line.rstrip("\n"))
                            if i >= 2:
                                break
                    learned.append("He generado un CSV con texto limpio. Muestra (fuente: %s):\n%s" % (src.name, "\n".join(head)))
    except Exception as e:
        learned.append("(nota) No pude previsualizar resultados: %s" % e)

    if not learned:
        learned.append("Ejecución completada. Revisa los logs de la orden para más detalles.")

    msg = "\n".join(learned)
    log_event("learned", msg, {"skill": skill})
    write_chat(session_root, "worker", msg)

    print("=== EJECUTANDO ===")
    print("=== RESUMEN APRENDIZAJE (ES) ===")
    print(msg)

if __name__ == "__main__":
    main()