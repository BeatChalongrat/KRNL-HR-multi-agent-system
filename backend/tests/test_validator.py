import asyncio, datetime
from db import init_db, SessionLocal, Employee
from agents.validator_agent import ValidatorAgent

def setup_module(module):
    init_db()

def test_validator_detects_errors():
    db = SessionLocal()
    e = Employee(name="A", email="bad", role="", start_date=datetime.date.today())
    db.add(e); db.commit(); db.refresh(e); db.close()

    agent = ValidatorAgent()
    out = asyncio.run(agent.run(e.id))
    assert "Invalid email format" in out["errors"]
    assert "Role is required" in out["errors"]
