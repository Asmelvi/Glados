from pathlib import Path
p = Path("tasks/sample_csv/input")
files = sorted(p.glob("*.csv"), key=lambda f: f.name)  # nombre asc
txt = "\n".join([f"{f.name},{f.stat().st_size}" for f in files]) + "\n"
Path("tasks/sample_csv/expected_stdout.txt").write_text(txt, encoding="utf-8")
print("expected regenerado OK")
