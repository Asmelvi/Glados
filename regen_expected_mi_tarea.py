from pathlib import Path
p = Path("tasks/mi_tarea/input")
files = sorted(p.glob("*.csv"), key=lambda f: f.stat().st_size, reverse=True)  # tamaño DESC
txt = "\n".join([f"{f.name},{f.stat().st_size}" for f in files]) + "\n"
Path("tasks/mi_tarea/expected_stdout.txt").write_text(txt, encoding="utf-8")
print("expected mi_tarea OK")
