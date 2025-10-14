# engine/sandbox_docker.py
from __future__ import annotations
import subprocess, shlex, time
from pathlib import Path
from typing import Dict, Any

IMAGE = "glados-runner:py312"  # <- fuerza nuestra imagen

def run_in_docker(
    workdir: str,
    input_dir: str,
    *,
    timeout_s: int = 15,
    cpus: float = 1.0,
    mem_mb: int = 256,
    network: str = "none",
    image: str = IMAGE,
) -> Dict[str, Any]:
    workdir = str(Path(workdir).resolve())
    input_dir = str(Path(input_dir).resolve())

    name = f"glados_once_{int(time.time()*1000)}"
    print(f"[docker] usando imagen no persistente: {image}")
    run_cmd = (
        f'docker run --rm --name {shlex.quote(name)} '
        f'--network {shlex.quote(network)} '
        f'--cpus {cpus} -m {mem_mb}m '
        f'-v "{workdir}:/app" -v "{input_dir}:/input" '
        f'{image} python /app/main.py /input'
    )
    t0 = time.time()
    proc = subprocess.run(run_cmd, shell=True, capture_output=True, text=True, timeout=timeout_s)
    dt = time.time() - t0
    return {
        "rc": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "time_s": dt,
        "peak_mb": 0.0,
    }
