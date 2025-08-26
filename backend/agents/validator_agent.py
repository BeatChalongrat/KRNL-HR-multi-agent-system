import re
from typing import Dict, Any
from agents.base import AgentBase
from db import SessionLocal, Employee
from agents.llm_utils import llm_normalize_employee

class ValidatorAgent(AgentBase):
    name = "Validator"

    async def run(self, employee_id: int) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            emp = db.get(Employee, employee_id)
            input_data = {
                "name": emp.name,
                "email": emp.email,
                "role": emp.role,
                "department": emp.department,
                "start_date": str(emp.start_date),
            }
            self.step("Loaded employee", input_data)

            errors = []
            if not re.match(r"[^@]+@[^@]+\.[^@]+", emp.email or ""):
                errors.append("Invalid email format")
            if not emp.name or len(emp.name.strip()) < 2:
                errors.append("Name too short")
            if not emp.role:
                errors.append("Role is required")

            self.step("Rule-based checks completed", {"errors": errors})

            llm_info = await llm_normalize_employee(input_data)
            self.step("LLM normalization", llm_info)

            output = {"errors": errors, "llm": llm_info}
            status = "OK" if not errors else "WARN"
            log_id = self.persist_log(employee_id, input_data, output, status=status)
            return {"log_id": log_id, **output}
        finally:
            db.close()
