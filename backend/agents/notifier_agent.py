# backend/agents/notifier_agent.py
from __future__ import annotations

import smtplib
import uuid
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# compatibility import: รองรับชื่อคลาสฐานหลายแบบ
try:
    from agents.base import BaseAgent  # ชื่อที่คาดหวัง
except Exception:
    try:
        from agents.base import AgentBase as BaseAgent  # ชื่อทางเลือก
    except Exception:
        try:
            from agents.base import Agent as BaseAgent  # อีกชื่อที่พบบ่อย
        except Exception:
            # fallback แบบไม่พึ่งอะไร (notifier_agent ไม่ใช้เมธอดจาก base)
            class BaseAgent:  # type: ignore
                pass
from db import SessionLocal, Employee, AgentLog
from settings import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM,
    DEFAULT_TZ,
    SIMULATE_INTEGRATIONS,
)


class NotifierAgent(BaseAgent):
    """
    Agent D — ส่งอีเมลต้อนรับ + แนบ .ics
    จุดเน้นเวอร์ชันนี้:
      - โทนอีเมล: Professional HR
      - Location ตรึงเป็น "Sukhumvit Hills"
      - ไม่มีการเรียก LLM
      - โค้ดปลอดภัย/ขั้นต่ำ เพื่อลดโอกาสล่ม
    """

    AGENT_NAME = "Notifier"

    async def run(self, employee_id: int):
        steps = []
        input_payload = {"employee_id": employee_id}

        db = SessionLocal()
        try:
            # 1) Load employee
            emp = db.get(Employee, employee_id)
            if not emp:
                return self._log_and_return(
                    db, employee_id, steps, input_payload,
                    output={"error": "Employee not found"},
                    status="ERROR",
                )
            steps.append({"description": "Loaded employee", "data": {"id": emp.id}})

            # 2) กำหนดช่วงเวลาประชุม (ถ้าไม่มีข้อมูลอื่น ให้ใช้ 09:00–10:00 ของ start_date)
            tz = DEFAULT_TZ or "Asia/Bangkok"
            start_dt = datetime.combine(emp.start_date, datetime.min.time()).replace(hour=9, minute=0, second=0)
            end_dt = start_dt + timedelta(hours=1)
            location = "Sukhumvit Hills"  # <— ตรึงตามที่ต้องการ

            # 3) สร้างข้อความอีเมล (ทางการ)
            subject, text_body, html_body = self._compose_email(emp, start_dt, end_dt, tz, location)
            steps.append({"description": "Composed email", "data": {"subject": subject, "location": location}})

            # 4) สร้างไฟล์ ICS
            ics_text = self._build_ics(
                summary=f"Day-1 Orientation: {emp.name}",
                start_dt=start_dt,
                end_dt=end_dt,
                attendee_email=emp.email,
                location=location,
                tz=tz,
            )
            steps.append({"description": "ICS built", "data": {"tz": tz}})

            # 5) ส่งอีเมล
            if SIMULATE_INTEGRATIONS:
                sent = {"channel": "console", "ok": True}
            else:
                self._send_email(emp.email, subject, text_body, html_body, ics_text)
                sent = {"channel": "email", "ok": True}
            steps.append({"description": "Notification sent", "data": sent})

            output = {
                "notification_id": int(f"{emp.id}01"),
                "message": text_body,  # เก็บข้อความที่ส่งจริง เพื่อการตรวจสอบ
                "sent": sent,
            }
            return self._log_and_return(db, employee_id, steps, input_payload, output=output, status="OK")

        except Exception as ex:
            return self._log_and_return(
                db, employee_id, steps, input_payload,
                output={"error": str(ex)},
                status="ERROR",
            )
        finally:
            db.close()

    # ---------------- helper methods ----------------

    def _compose_email(self, emp: Employee, start_dt: datetime, end_dt: datetime, tz: str, location: str):
        """คืนค่า (subject, text_body, html_body) โทนทางการ"""
        start_local = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_local = end_dt.strftime("%Y-%m-%d %H:%M:%S")

        subject = "Welcome to KRNL — Day-1 Orientation Details"

        text_body = f"""Dear {emp.name},

We are pleased to confirm your commencement at KRNL as {emp.role} on {emp.start_date}.
Please find the details of your Day-1 orientation below:

• Date & Time: {start_local} – {end_local} ({tz})
• Location: {location}

A calendar invitation (.ics) is attached. Kindly accept the invite so it is added to your calendar.
Should you have any questions prior to your start date, please reply to this email.

Kind regards,
KRNL Human Resources
"""

        html_body = f"""\
<html>
  <body style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#111;line-height:1.5">
    <p>Dear {emp.name},</p>
    <p>We are pleased to confirm your commencement at <b>KRNL</b> as <b>{emp.role}</b> on <b>{emp.start_date}</b>.</p>
    <p>Please find the details of your <b>Day-1 orientation</b> below:</p>
    <p>
      • <b>Date &amp; Time</b>: {start_local} – {end_local} ({tz})<br/>
      • <b>Location</b>: {location}
    </p>
    <p>A calendar invitation (.ics) is attached. Kindly accept the invite so it is added to your calendar.</p>
    <p>Should you have any questions prior to your start date, please reply to this email.</p>
    <p>Kind regards,<br/>KRNL Human Resources</p>
  </body>
</html>
"""
        return subject, text_body, html_body

    def _build_ics(self, summary: str, start_dt: datetime, end_dt: datetime, attendee_email: str, location: str, tz: str):
        """สร้างเนื้อหา ICS ใช้ method=REQUEST (ปลอดภัยสำหรับ MIME)"""
        uid = uuid.uuid4().hex
        dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
        dtend = end_dt.strftime("%Y%m%dT%H%M%S")

        ics = f"""BEGIN:VCALENDAR
PRODID:-//KRNL Onboarding//EN
VERSION:2.0
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
SUMMARY:{summary}
DTSTART;TZID={tz}:{dtstart}
DTEND;TZID={tz}:{dtend}
LOCATION:{location}
DESCRIPTION:Welcome & IT setup
ORGANIZER:MAILTO:{SMTP_FROM}
ATTENDEE;CN={attendee_email};RSVP=TRUE:MAILTO:{attendee_email}
END:VEVENT
END:VCALENDAR
"""
        return ics

    def _send_email(self, to_email: str, subject: str, text_body: str, html_body: str, ics_text: str):
        """ส่งเมล + แนบ .ics (แก้ MIME subtype ให้ปลอดภัย)"""
        msg = MIMEMultipart("mixed")
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(text_body, "plain", "utf-8"))
        alt.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt)

        # สร้างพาร์ต calendar อย่างถูกต้อง: ใช้ subtype="calendar" แล้ว replace header เป็น method=REQUEST
        cal_part = MIMEText(ics_text, _subtype="calendar", _charset="UTF-8")
        cal_part.replace_header("Content-Type", "text/calendar; method=REQUEST; charset=UTF-8")
        cal_part.add_header("Content-Disposition", 'attachment; filename="invite.ics"')
        cal_part.add_header("Content-Class", "urn:content-classes:calendarmessage")
        msg.attach(cal_part)

        with smtplib.SMTP(SMTP_HOST, int(SMTP_PORT)) as s:
            s.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(SMTP_FROM, [to_email], msg.as_string())

    def _log_and_return(self, db, employee_id, steps, input_payload, output, status="OK"):
        log = AgentLog(
            employee_id=employee_id,
            agent=self.AGENT_NAME,
            input=input_payload,
            steps=steps,
            output=output,
            status=status,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return {"log_id": log.id, **(output or {})}
