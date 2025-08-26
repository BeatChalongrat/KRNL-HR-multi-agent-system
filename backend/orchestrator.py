from typing import List
from db import SessionLocal, Employee
from agents.validator_agent import ValidatorAgent
from agents.account_agent import AccountAgent
from agents.notifier_agent import NotifierAgent


class Orchestrator:
    def __init__(self):
        self.validator = ValidatorAgent()
        self.account = AccountAgent()
        self.notifier = NotifierAgent()

    async def run(self, employee_id: int) -> List[int]:
        """
        Canonical entrypoint for the pipeline.
        Runs agents (Validator -> Account -> Notifier) and returns a list of log_ids.
        NOTE: Status transitions are handled in main.py; this method avoids
        mutating Employee.status to prevent conflicts with the API layer.
        """
        trace: List[int] = []

        # Ensure employee exists (fail fast with a clear error)
        db = SessionLocal()
        try:
            emp = db.get(Employee, employee_id)
            if not emp:
                raise ValueError(f"Employee {employee_id} not found")
        finally:
            db.close()

        # A -> Validator
        a = await self.validator.run(employee_id)
        trace.append(a["log_id"])

        # B -> Account  (does A2A call to Scheduler internally)
        b = await self.account.run(employee_id)
        trace.append(b["log_id"])

        # D -> Notifier
        d = await self.notifier.run(employee_id)
        trace.append(d["log_id"])

        return trace

    # Back-compat with older code calling run_pipeline()
    async def run_pipeline(self, employee_id: int) -> List[int]:
        return await self.run(employee_id)

    # Allow: await orchestrator(employee_id)
    async def __call__(self, employee_id: int) -> List[int]:
        return await self.run(employee_id)


orchestrator = Orchestrator()
