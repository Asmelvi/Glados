# engine/sandbox_docker_persistent.py
from __future__ import annotations
import subprocess, shlex, uuid, time
from pathlib import Path
from typing import Optional, Dict, Any

class DockerSandbox:
    """
    Mantiene un contenedor Docker vivo y ejecuta 'python main.py /input' vía `docker exec`.
    - Monta /app (workdir del experimento) RW
    - Monta /input (carpeta de datos) RO
    - Limita CPU/RAM
    - Red configurable ("none" para sin internet, "bridge" para permitir)
    """

    def __init__(
        self,
        workdir: str,
        root_dir_abs: str,
        *,
        image: str = "glados-runner:py312",
        cpus: float = 1.0,
        mem_mb: int = 256,
        network: str = "none",   # "none" (sin internet) o "bridge" (con internet)
        name: Optional[str] = None,
    ) -> None:
        self.workdir = str(Path(workdir).resolve())
        self.root_dir_abs = str(Path(root_dir_abs).resolve())
        self.image = image
        self.cpus = cpus
        self.mem_mb = mem_mb
        self.network = network
        self.name = name or f"glados_persist_{uuid.uuid4().hex[:8]}"
        self._started = False

    def _run(self, cmd_list: list[str]) -> subprocess.CompletedProcess:
        # Utilidad interna para ejecutar comandos del host
        return subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            check=False,
        )

    def start(self) -> None:
        if self._started:
            return

        Path(self.workdir).mkdir(parents=True, exist_ok=True)

        run_cmd = [
            "docker", "run", "-d", "--rm",
            "--name", self.name,
            "--cpus", str(self.cpus),
            "-m", f"{self.mem_mb}m",
            "--network", self.network,
            "-v", f"{self.workdir}:/app",
            "-v", f"{self.root_dir_abs}:/input:ro",
            "-w", "/app",
            self.image,
            "sh", "-lc", "sleep infinity"
        ]
        res = self._run(run_cmd)
        if res.returncode != 0:
            raise RuntimeError(
                f"Docker run failed (image={self.image}):\n"
                f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
            )
        self._started = True

    def exec_python(self, args: list[str], timeout_s: int = 15) -> Dict[str, Any]:
        """
        Ejecuta `python -u <args...>` dentro del contenedor.
        Devuelve: rc, stdout, stderr, time_s, peak_mb
        """
        if not self._started:
            raise RuntimeError("Sandbox not started. Call start() first.")

        # Construimos la línea de shell dentro del contenedor
        # Ejemplo: python -u main.py /input
        inner = "python -u " + " ".join(shlex.quote(a) for a in args)
        cmd = ["docker", "exec", "-i", self.name, "sh", "-lc", f"cd /app && {inner}"]

        t0 = time.perf_counter()
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        dt = time.perf_counter() - t0

        return {
            "rc": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "time_s": dt,      # ahora medimos tiempo real
            "peak_mb": 0.0,    # sin medición de memoria por ahora
        }

    def stop(self) -> None:
        if not self._started:
            return
        # Intenta parar/limpiar el contenedor
        self._run(["docker", "rm", "-f", self.name])
        self._started = False
