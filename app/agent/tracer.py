"""
Records timestamped execution steps so the frontend can show the user real-time progress while the pipeline runs (planning -> searching -> cleaning -> synthesizing -> done)
Each pipeline step calls tracer.log(step, detail) to add an entry.
At the end, tracer.get_steps() returns the full list for the response.
"""

from datetime import datetime, timezone       # timezone-aware timestamps for consistent display
from app.schemas import TraceStep

class Tracer:   # Accumulates TraceStep objects throughout the pipeline execution

    def __init__(self):
        self.steps: list[TraceStep] = []       # ordered list of execution steps

    def log(self, step: str, detail: str) -> None:       # record a new pipeline step with the current UTC timestamp
        self.steps.append(TraceStep(
            timestamp=datetime.now(timezone.utc).isoformat(),       # e.g. "2026-11-15T10:30:45.123456+00:00"
            step=step,
            detail=detail,
        ))

    def get_steps(self) -> list[TraceStep]:       # return all recorded steps (used by main.py to build AgentResponse)
        return self.steps