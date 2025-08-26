import secrets
from typing import Dict, Any
from agents.base import AgentBase
from db import SessionLocal, Employee, Account
from sqlalchemy.orm import Session

ROLE_PERMISSIONS = {
    "AI Engineer": ["repo:read", "inference:run", "data:read"],
    "Backend Engineer": ["repo:read", "deploy:trigger"],
    "HR": ["employee:read", "employee:write"],
}

class AccountAgent(AgentBase):
    name = "Account"

    def _username(self, name: str) -> str:
        base = "".join([c.lower() for c in name if c.isalnum()])[:10] or "user"
        return base + secrets.token_hex(2)

    def _perms(self, role: str):
        return ROLE_PERMISSIONS.get(role, ["repo:read"])

    def _create(self, db: Session, emp: Employee) -> Account:
        username = self._username(emp.name)
        password = secrets.token_urlsafe(10)
        acc = Account(
            employee_id=emp.id,
            username=username,
            temp_password=password,
            permissions=self._perms(emp.role),
        )
        db.add(acc)
        db.commit()
        db.refresh(acc)
        return acc

    async def run(self, employee_id: int) -> Dict[str, Any]:
        self.start_run()
        db = SessionLocal()
        try:
            emp = db.get(Employee, employee_id)
            self.step("Loaded employee", {"id": emp.id, "name": emp.name})

            # ✅ Idempotent: reuse existing account if already created
            existing = db.query(Account).filter_by(employee_id=emp.id).first()
            if existing:
                acc = existing
                self.step("Account already exists", {"username": acc.username})
            else:
                acc = self._create(db, emp)
                self.step("Account created", {"username": acc.username})

            # A2A: call Scheduler (Scheduler จะกันซ้ำอีกชั้นเอง)
            from agents.scheduler_agent import SchedulerAgent
            sched = SchedulerAgent()
            sres = await sched.run(employee_id)
            self.step("A2A call to Scheduler completed", {"scheduler_log_id": sres["log_id"]})

            output = {"username": acc.username, "permissions": acc.permissions}
            log_id = self.persist_log(employee_id, {"employee_id": emp.id}, output, status="OK")
            return {"log_id": log_id, **output}
        finally:
            db.close()
