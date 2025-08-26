from typing import Dict, Any, List
from db import SessionLocal, AgentLog

class AgentBase:
    name: str = "BaseAgent"

    def __init__(self):
        self.steps: List[Dict[str, Any]] = []

    def start_run(self) -> None:
        """Reset steps for every run to avoid step accumulation."""
        self.steps = []

    def step(self, description: str, data: Any = None) -> None:
        self.steps.append({"description": description, "data": data})

    def persist_log(
        self,
        employee_id: int,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        status: str = "OK",
    ) -> int:
        db = SessionLocal()
        try:
            log = AgentLog(
                employee_id=employee_id,
                agent=self.name,
                input=input_data,
                steps=self.steps,
                output=output_data,
                status=status,
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            return log.id
        finally:
            db.close()
            # Ensure steps are cleared after persisting as well
            self.steps = []
