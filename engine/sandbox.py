# engine/sandbox.py
import subprocess, time, threading, psutil
from typing import List, Dict, Any

def run(cmd: List[str], cwd: str, timeout_s: int = 30) -> Dict[str, Any]:
    start = time.perf_counter()
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    p = psutil.Process(proc.pid)
    peak_mb = 0.0
    stop_flag = False

    def monitor():
        nonlocal peak_mb, stop_flag
        try:
            while not stop_flag:
                try:
                    rss = p.memory_info().rss / (1024 * 1024)
                    if rss > peak_mb:
                        peak_mb = rss
                except psutil.Error:
                    break
                time.sleep(0.05)
        except Exception:
            pass

    t = threading.Thread(target=monitor, daemon=True)
    t.start()

    try:
        out, err = proc.communicate(timeout=timeout_s)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err, rc = "", "TIMEOUT", -9
    finally:
        stop_flag = True
        t.join(timeout=0.2)

    wall = time.perf_counter() - start
    return {"rc": rc, "stdout": out, "stderr": err, "time_s": wall, "peak_mb": peak_mb}
