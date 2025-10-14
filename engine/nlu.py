# engine/nlu.py
from .types import TaskSpec

def parse_spanish(text: str) -> TaskSpec:
    text_low = text.lower()
    spec = TaskSpec(goal=text.strip())
    if "csv" in text_low:
        spec.inputs = ["ruta"]
        spec.io_contract = {"stdout": "lista_csv_ordenados"}
        # por defecto
        sort_by, order = "size", "desc"
        # detecta "nombre"/"alfabético"
        if "nombre" in text_low or "alfab" in text_low:
            sort_by = "name"
        # detecta asc/desc
        if "ascend" in text_low:
            order = "asc"
        elif "descend" in text_low:
            order = "desc"
        spec.constraints = {"sort_by": sort_by, "order": order}
    return spec