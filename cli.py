# cli.py
from __future__ import annotations

import argparse
from pathlib import Path
from jinja2 import Template


def generate_from_template(template_path: str, out_path: str, context: dict) -> str:
    tpl = Path(template_path).read_text(encoding="utf-8")
    code = Template(tpl).render(**context)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(code, encoding="utf-8")
    return code


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["local", "docker"], default="docker")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--repeats", type=int, default=1, help="Repeticiones por candidato (para mediana).")
    ap.add_argument("--task-dir", default="tasks/mi_tarea/input")
    ap.add_argument("--expected", default="tasks/mi_tarea/expected_stdout.txt")
    ap.add_argument("--workdir", default="workspace/exp_mi_tarea")
    ap.add_argument("--cpus", type=float, default=1.0)
    ap.add_argument("--mem", type=int, default=256, help="MB de RAM para Docker")
    ap.add_argument("--persistent", action="store_true")
    ap.add_argument("--allow-net", action="store_true")
    ap.add_argument("--template", default="engine/codegen/templates/csv_pipeline.py.j2")
    ap.add_argument(
        "--recipes",
        default="",
        help="Lista separada por comas de recetas a probar (override de las por defecto)",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Timeout por ejecución (segundos) para cada trial dentro del sandbox.",
    )

    args = ap.parse_args()

    # Render de plantilla (las web no necesitan contexto)
    ctx = {}
    out_seed = Path("workspace/main_seed.py")
    generate_from_template(args.template, str(out_seed), ctx)

    # Paths absolutos
    root_abs = str(Path(args.task_dir).resolve())
    expected_abs = str(Path(args.expected).resolve())

    # Parse de recetas desde CLI (si se pasan)
    recipes_cli = None
    if args.recipes.strip():
        recipes_cli = [r.strip() for r in args.recipes.split(",") if r.strip()]

    # Llama a evolve
    from engine.evolve import evolve

    score = evolve(
        seed_code=out_seed.read_text(encoding="utf-8"),
        workdir=args.workdir,
        expected_stdout_file=expected_abs,
        rounds=args.rounds,
        root_dir=root_abs,
        verbose=True,
        backend=args.backend,
        cpus=args.cpus,
        mem_mb=args.mem,
        persistent=args.persistent,
        allow_net=args.allow_net,
        repeats=args.repeats,
        recipes=recipes_cli,     # override si se pasa
        timeout_s=args.timeout,  # <-- NUEVO: timeout parametrizable
    )
    print(f"Fitness final: {score}")
