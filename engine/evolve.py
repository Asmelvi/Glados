# engine/evolve.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from statistics import median

from .codegen.edits_ast import ast_mutate
from .evaluator import evaluate_rel

# Recetas por defecto (puedes override desde CLI)
# Incluye recetas de CSV + web
DEFAULT_RECIPES: List[str] = [
    "multiprocessing_sizes",
    "threaded_stat",
    "use_scandir",
    # Web
    "threaded_fetch",
    "add_retry_headers",
    "disk_cache",
]


def _exec_once_local(workdir: Path, root_dir_abs: str, timeout_s: int):
    from .sandbox import run as run_local
    return run_local(["python", "main.py", root_dir_abs], cwd=str(workdir), timeout_s=timeout_s)


def _exec_once_docker(
    workdir: Path,
    root_dir_abs: str,
    timeout_s: int,
    cpus: float,
    mem_mb: int,
    allow_net: bool,
):
    # Runner no persistente (fallback)
    from .sandbox_docker import run_in_docker as run_docker
    # Nota: el runner no persistente no usa 'network' explícito aquí
    return run_docker(str(workdir), root_dir_abs, timeout_s=timeout_s, cpus=cpus, mem_mb=mem_mb)


def _trial_once(
    code: str,
    workdir: Path,
    expected_abs: str,
    *,
    executor,
    base_time_s: Optional[float],
    base_peak_mb: Optional[float],
    timeout_s: int = 15,
) -> Tuple[Dict[str, Any], str, str, int]:
    """
    Escribe main.py, ejecuta UNA vez con 'executor', evalúa y loguea métricas.
    """
    main_py = workdir / "main.py"
    main_py.write_text(code, encoding="utf-8")

    res = executor(timeout_s=timeout_s)  # dict con rc, stdout, stderr, time_s, peak_mb

    (workdir / "last_stdout.txt").write_text(res.get("stdout", ""), encoding="utf-8")
    (workdir / "last_stderr.txt").write_text(res.get("stderr", ""), encoding="utf-8")

    if res["rc"] == 0:
        metrics = evaluate_rel(
            res.get("stdout", ""),
            expected_abs,
            res.get("time_s", 0.0),
            res.get("peak_mb", 0.0),
            base_time_s=base_time_s,
            base_peak_mb=base_peak_mb,
        )
    else:
        metrics = {
            "correct": 0.0,
            "time_s": res.get("time_s", 0.0),
            "peak_mb": res.get("peak_mb", 0.0),
            "score": 0.0,
        }

    # Log JSONL de cada ejecución
    try:
        import json

        with open(workdir / "metrics.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"metrics": metrics, "rc": res["rc"]}) + "\n")
    except Exception:
        pass

    return metrics, res.get("stdout", ""), res.get("stderr", ""), res["rc"]


def _aggregate_metrics(metrics_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Agrega varias mediciones del mismo candidato:
    - correct = min(corrects) (conservador)
    - time_s  = mediana
    - score   = mediana (si está presente)
    - peak_mb = mediana de valores > 0 (si hay)
    """
    if not metrics_list:
        return {"correct": 0.0, "time_s": 9e9, "peak_mb": 0.0, "score": 0.0}

    corrects = [m.get("correct", 0.0) for m in metrics_list]
    times = [m.get("time_s", 0.0) for m in metrics_list]
    scores = [m.get("score", 0.0) for m in metrics_list]
    peaks = [m.get("peak_mb", 0.0) for m in metrics_list if m.get("peak_mb", 0.0) > 0]

    agg = dict(metrics_list[-1])  # base
    agg["correct"] = min(corrects)
    agg["time_s"] = median(times) if times else 9e9
    agg["score"] = median(scores) if scores else 0.0
    agg["peak_mb"] = median(peaks) if peaks else (metrics_list[-1].get("peak_mb", 0.0) or 0.0)
    return agg


def evolve(
    seed_code: str,
    workdir: str,
    expected_stdout_file: str,
    rounds: int = 2,
    root_dir: str = "tasks/sample_csv/input",
    verbose: bool = True,
    backend: str = "docker",   # "docker" o "local"
    cpus: float = 1.0,
    mem_mb: int = 256,
    persistent: bool = True,   # contenedor persistente por defecto
    allow_net: bool = False,   # internet deshabilitado por defecto
    repeats: int = 1,          # repeticiones por candidato (mediana)
    recipes: Optional[List[str]] = None,  # override de recetas
    timeout_s: int = 15,       # <-- NUEVO: timeout parametrizable para cada trial
) -> float:
    """
    Evolución con baseline relativo. Si backend=docker y persistent=True,
    mantiene un contenedor vivo y ejecuta via docker exec (rápido).
    """
    path = Path(workdir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    expected_abs = str(Path(expected_stdout_file).resolve())
    root_dir_abs = str(Path(root_dir).resolve())

    if verbose:
        print(f"[paths] workdir={path}")
        print(f"[paths] root_dir_abs={root_dir_abs}")
        print(f"[paths] expected_abs={expected_abs}")
        print(f"[backend] {backend}  persistent={persistent}  allow_net={allow_net}")

    # --- Prepara executor ---
    sandbox = None
    if backend == "docker" and persistent:
        from .sandbox_docker_persistent import DockerSandbox

        network = "bridge" if allow_net else "none"
        sandbox = DockerSandbox(str(path), root_dir_abs, cpus=cpus, mem_mb=mem_mb, network=network)
        sandbox.start()

        def _exec(timeout_s: int):
            # el runner persistente devuelve time_s real
            return sandbox.exec_python(["main.py", "/input"], timeout_s=timeout_s)

    elif backend == "docker":
        def _exec(timeout_s: int):
            return _exec_once_docker(path, root_dir_abs, timeout_s, cpus, mem_mb, allow_net)
    else:
        def _exec(timeout_s: int):
            return _exec_once_local(path, root_dir_abs, timeout_s)

    # --- Baseline (una vez) ---
    best_code = seed_code
    base_metrics, out, err, rc = _trial_once(
        best_code,
        path,
        expected_abs,
        executor=_exec,
        base_time_s=None,
        base_peak_mb=None,
        timeout_s=timeout_s,   # <-- usa el timeout recibido
    )
    if verbose:
        print(f"[baseline] rc={rc} metrics={base_metrics}")

    base_time_s = base_metrics["time_s"]
    base_peak_mb = base_metrics.get("peak_mb", 0.0) or None
    best_metrics = base_metrics

    # --- Lista de recetas ---
    active_recipes = list(recipes) if recipes else list(DEFAULT_RECIPES)

    # --- Rondas de evolución ---
    try:
        for r in range(1, rounds + 1):
            if verbose:
                print(f"[round {r}] ------------------------------")
            for rec in active_recipes:
                cand = ast_mutate(best_code, rec)

                # Ejecuta N repeticiones y agrega por mediana
                reps_metrics: List[Dict[str, Any]] = []
                last_rc = 0
                for _ in range(max(1, repeats)):
                    m, out, err, rc = _trial_once(
                        cand,
                        path,
                        expected_abs,
                        executor=_exec,
                        base_time_s=base_time_s,
                        base_peak_mb=base_peak_mb,
                        timeout_s=timeout_s,  # <-- igual aquí
                    )
                    reps_metrics.append(m)
                    last_rc = rc

                agg = _aggregate_metrics(reps_metrics)

                if verbose:
                    print(f"  recipe={rec:>24}  rc={last_rc}  metrics={agg}")

                # Escoge si mejora: primero correct, luego score
                if (agg["correct"] > best_metrics["correct"]) or (agg["score"] > best_metrics["score"]):
                    best_metrics = agg
                    best_code = cand
                    (path / "main.py").write_text(best_code, encoding="utf-8")
                    (path / "best_stdout.txt").write_text(out, encoding="utf-8")
                    (path / "best_stderr.txt").write_text(err, encoding="utf-8")
    finally:
        if sandbox:
            sandbox.stop()

    # Guarda el mejor código
    (path / "main.py").write_text(best_code, encoding="utf-8")

    # Leaderboard (apéndice jsonl)
    try:
        import json, time
        summary = {
            "ts": time.time(),
            "task_root": root_dir,
            "expected": expected_stdout_file,
            "backend": backend,
            "persistent": persistent,
            "allow_net": allow_net,
            "cpus": cpus,
            "mem_mb": mem_mb,
            "rounds": rounds,
            "repeats": repeats,
            "timeout_s": timeout_s,
            "recipes": active_recipes,
            "best": best_metrics,
        }
        with open(Path(workdir) / "leaderboard.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(summary) + "\n")
    except Exception:
        pass

    if verbose:
        print(f"[best] {best_metrics}")
    return best_metrics["score"]
