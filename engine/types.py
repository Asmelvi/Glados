from pydantic import BaseModel, Field
from typing import List, Dict, Any

class TaskSpec(BaseModel):
    goal: str = Field(...)
    inputs: List[str] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    metric: str = 'correctness'
    timeout_s: int = 30
    io_contract: Dict[str, Any] = Field(default_factory=dict)

class Plan(BaseModel):
    steps: List[Dict[str, Any]]
    artifacts: Dict[str, str]
