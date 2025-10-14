# engine/evaluator.py
import re

def _normalize_lines(s: str):
    return [re.sub(r"\s+$", "", x) for x in s.replace("\r\n","\n").replace("\r","\n").split("\n") if x != ""]

def correctness(stdout: str, expected_path: str) -> float:
    exp = _normalize_lines(open(expected_path, encoding="utf-8").read())
    got = _normalize_lines(stdout)
    return 1.0 if got == exp else 0.0

def eval_lines_set(got: str, expected_file: str) -> float:
    """Compara conjuntos de líneas, ignorando orden y espacios finales."""
    exp = Path(expected_file).read_text(encoding="utf-8").splitlines()
    g   = got.splitlines()
    norm = lambda xs: {x.strip() for x in xs if x.strip() != ""}
    return 1.0 if norm(exp) == norm(g) else 0.0

def evaluate_rel(stdout: str, expected_path: str, time_s: float, peak_mb: float,
                 base_time_s: float | None = None, base_peak_mb: float | None = None) -> dict:
    """
    Score relativo al baseline:
      - correctitud manda: si no es 1.0, el score cae fuerte.
      - si base_time_s está definido: t_gain = (base_time - time)/base_time, clamp 0..1
      - si base_peak_mb > 0: m_gain similar; si no, m_gain = 0 (Docker)
      - mezcla: 60% tiempo, 40% memoria
      - score final en [0.5, 1.0] cuando correct=1.0 (0.5 baseline, sube con mejoras)
    """
    corr = correctness(stdout, expected_path)
    if corr < 1.0:
        return {"correct": corr, "time_s": time_s, "peak_mb": peak_mb, "score": 0.0}

    def clamp01(x): return 0.0 if x < 0 else (1.0 if x > 1 else x)

    if base_time_s and base_time_s > 0:
        t_gain = clamp01((base_time_s - time_s) / base_time_s)
    else:
        t_gain = 0.0

    if base_peak_mb and base_peak_mb > 0:
        m_gain = clamp01((base_peak_mb - peak_mb) / base_peak_mb)
    else:
        m_gain = 0.0  # en Docker no medimos peak_mb externo

    aux = 0.6 * t_gain + 0.4 * m_gain
    # baseline = 0.5; mejoras empujan hasta 1.0
    total = corr * (0.5 + 0.5 * aux)
    return {"correct": corr, "time_s": time_s, "peak_mb": peak_mb, "score": total}

