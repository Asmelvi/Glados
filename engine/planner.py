from .types import TaskSpec, Plan

def make_plan(spec: TaskSpec) -> Plan:
    steps = [
        {'name': 'generate_code', 'template': 'csv_pipeline.py.j2'},
        {'name': 'run', 'cmd': ['python', 'main.py'], 'timeout_s': spec.timeout_s},
        {'name': 'evaluate', 'metric': spec.metric}
    ]
    artifacts = {'main.py': 'workspace/main.py'}
    return Plan(steps=steps, artifacts=artifacts)
