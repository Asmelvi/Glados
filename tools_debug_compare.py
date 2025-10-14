from pathlib import Path

exp_path = Path("tasks/mi_tarea/expected_stdout.txt")
got_path = Path("workspace/exp_mi_tarea/last_stdout.txt")

exp = exp_path.read_text(encoding="utf-8").splitlines()
got = got_path.read_text(encoding="utf-8").splitlines()

print("=== EXPECTED ===")
print("\n".join(exp))
print("=== GOT ===")
print("\n".join(got))

ok = (exp == got)
print("Equal? ->", ok)
if not ok:
    i = next((i for i,(a,b) in enumerate(zip(exp,got)) if a!=b), None)
    if i is not None:
        print(f"First diff at line {i+1}:")
        print("  expected:", repr(exp[i]))
        print("  got     :", repr(got[i]))
    else:
        print(f"Different lengths: expected={len(exp)} got={len(got)}")
