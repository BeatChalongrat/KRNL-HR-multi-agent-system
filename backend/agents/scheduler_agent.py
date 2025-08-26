from typing import Dict, Any
from agents.base import AgentBase
from db import SessionLocal, Employee, CalendarEvent
from settings import SIMULATE_INTEGRATIONS, DEFAULT_TZ, DEFAULT_LOCATION
from agents.llm_utils import llm_propose_orientation_event, have_llm

class SchedulerAgent(AgentBase):
    name = "Scheduler"

    async def run(self, employee_id: int) -> Dict[str, Any]:
        self.start_run()
        db = SessionLocal()
        try:
            emp = db.get(Employee, employee_id)
            self.step("Loaded employee", {"id": emp.id, "start_date": str(emp.start_date)})

            existing = db.query(CalendarEvent).filter_by(employee_id=emp.id).first()
            if existing:
                self.step("Calendar event already exists", {"calendar_event_id": existing.id})
                ce = existing
            else:
                event = None
                if have_llm():
                    ai = await llm_propose_orientation_event(emp.name, emp.email, str(emp.start_date), emp.role, tz=DEFAULT_TZ or "Asia/Bangkok")
                    if isinstance(ai, dict) and "start" in ai and "end" in ai:
                        event = {
                            "summary": f"Day-1 Orientation: {emp.name}",
                            "start": {"dateTime": ai["start"].get("dateTime"), "timeZone": ai["start"].get("timeZone", DEFAULT_TZ)},
                            "end":   {"dateTime": ai["end"].get("dateTime"), "timeZone": ai["end"].get("timeZone", DEFAULT_TZ)},
                            "attendees": [{"email": emp.email}],
                            "location": ai.get("location", DEFAULT_LOCATION or "HQ – Room A"),
                            "description": ai.get("description", "Welcome & IT setup"),
                            "status": "confirmed",
                            "simulate": SIMULATE_INTEGRATIONS,
                        }
                        self.step("AI-proposed event", {"start": event["start"], "end": event["end"], "location": event["location"]})
                if not event:
                    event = {
                        "summary": f"Day-1 Orientation: {emp.name}",
                        "start": {"dateTime": f"{emp.start_date}T10:00:00", "timeZone": DEFAULT_TZ or "Asia/Bangkok"},
                        "end":   {"dateTime": f"{emp.start_date}T11:00:00", "timeZone": DEFAULT_TZ or "Asia/Bangkok"},
                        "attendees": [{"email": emp.email}],
                        "location": DEFAULT_LOCATION or "HQ – Room A",
                        "description": "Welcome & IT setup",
                        "status": "confirmed",
                        "simulate": SIMULATE_INTEGRATIONS,
                    }
                ce = CalendarEvent(employee_id=emp.id, event_json=event)
                db.add(ce); db.commit(); db.refresh(ce)
                self.step("Calendar event created", event)

            output = {"calendar_event_id": ce.id, "event": ce.event_json}
            log_id = self.persist_log(employee_id, {"employee_id": emp.id}, output, status="OK")
            return {"log_id": log_id, **output}
        finally:
            db.close()
