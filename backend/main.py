import io
import os
import csv
import asyncio
from datetime import date, datetime
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from db import init_db, SessionLocal, Employee, AgentLog
from orchestrator import orchestrator
from settings import API_HOST, API_PORT, API_LOG_LEVEL

# ---------- App ----------
app = FastAPI(title="KRNL Onboarding")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# static
app.mount("/static", StaticFiles(directory="static"), name="static")

# init DB at startup
init_db()


# ---------- Helpers ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _parse_date(s: str) -> date:
    """Support YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY."""
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    # try ISO loose
    try:
        return date.fromisoformat(s)
    except Exception:
        raise ValueError("Invalid date format (use YYYY-MM-DD, DD/MM/YYYY, or MM/DD/YYYY)")


# ---------- API: UI ----------
@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse("static/index.html")


# ---------- API: Employees ----------
@app.get("/api/employees")
def list_employees(db=Depends(get_db)):
    items = db.query(Employee).order_by(Employee.id.desc()).all()
    out = []
    for e in items:
        out.append({
            "id": e.id,
            "name": e.name,
            "email": e.email,
            "role": e.role,
            "department": e.department or "-",
            "start_date": e.start_date.isoformat(),
            "status": e.status or "PENDING",
        })
    return out


@app.post("/api/employees")
def create_employee(
    name: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    department: str = Form(""),
    start_date: str = Form(...),
    db=Depends(get_db),
):
    try:
        sd = _parse_date(start_date)
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))

    e = Employee(
        name=name.strip(),
        email=email.strip(),
        role=role.strip(),
        department=(department or "").strip() or None,
        start_date=sd,
        status="PENDING",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return {"ok": True, "id": e.id}


@app.delete("/api/employees/{employee_id}")
def delete_employee(employee_id: int, db=Depends(get_db)):
    e = db.get(Employee, employee_id)
    if not e:
        raise HTTPException(status_code=404, detail="Employee not found")
    # manual cascade for logs (extend if you have other tables)
    db.query(AgentLog).filter(AgentLog.employee_id == employee_id).delete(synchronize_session=False)
    db.delete(e)
    db.commit()
    return {"ok": True}


# ---------- API: CSV Upload / Sample ----------
@app.post("/api/employees/upload_csv")
async def upload_csv(file: UploadFile = File(...), db=Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")

    content = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))
    required = {"name", "email", "role", "start_date"}
    missing = [h for h in required if h not in reader.fieldnames]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing headers: {', '.join(missing)}")

    inserted = skipped = errors = 0
    error_rows: List[Dict[str, Any]] = []

    for idx, row in enumerate(reader, start=2):  # start=2 to account for header line
        try:
            name = (row.get("name") or "").strip()
            email = (row.get("email") or "").strip()
            role = (row.get("role") or "").strip()
            department = (row.get("department") or "").strip() or None
            sd = _parse_date(row.get("start_date") or "")

            if not name or not email or not role:
                skipped += 1
                continue

            # idempotent-ish: skip if same email & start_date already exists
            exists = (
                db.query(Employee)
                .filter(Employee.email == email, Employee.start_date == sd)
                .first()
            )
            if exists:
                skipped += 1
                continue

            e = Employee(
                name=name,
                email=email,
                role=role,
                department=department,
                start_date=sd,
                status="PENDING",
            )
            db.add(e)
            inserted += 1
        except Exception as ex:
            errors += 1
            error_rows.append({"line": idx, "error": str(ex)})
    db.commit()

    return {
        "ok": True,
        "summary": {"inserted": inserted, "skipped": skipped, "errors": errors},
        "errors": error_rows[:50],
    }


@app.get("/api/employees/sample_csv")
def download_sample_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "email", "role", "department", "start_date"])
    w.writerow(["Ada Lovelace", "ada@krnl.example", "AI Engineer", "R&D", "2025-09-01"])
    w.writerow(["Chalongrat", "chalongrat@ctc-g.co.th", "AI Engineer", "AI", "2025-08-25"])
    data = buf.getvalue().encode("utf-8")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="onboarding_sample.csv"'},
    )


# ---------- API: Orchestrate (sets status) ----------
@app.post("/api/run/{employee_id}")
async def run_onboarding(employee_id: int, db=Depends(get_db)):
    e = db.get(Employee, employee_id)
    if not e:
        raise HTTPException(status_code=404, detail="Employee not found")
    try:
        # โชว์สถานะ RUNNING ทันที
        e.status = "RUNNING"
        db.commit()

        # ---------- เรียก orchestrator แบบป้องกันทุกกรณี ----------
        res = None

        # ถ้ามีเมธอด .run ให้ใช้ .run(...)
        target = getattr(orchestrator, "run", None)
        if callable(target):
            maybe = target(employee_id)
        # ถ้า orchestrator ตัวมันเอง callable (เป็นฟังก์ชัน/คอร์รุตีน)
        elif callable(orchestrator):
            maybe = orchestrator(employee_id)
        else:
            raise TypeError("Invalid orchestrator: has neither .run(...) nor is callable")

        # รองรับทั้ง sync/async
        res = await maybe if asyncio.iscoroutine(maybe) else maybe
        # -----------------------------------------------------------

        # สำเร็จ
        e = db.get(Employee, employee_id)
        if e:
            e.status = "COMPLETED"
            db.commit()
        return {"ok": True, "result": res}

    except Exception as ex:
        # ล้มเหลว
        db.rollback()
        e = db.get(Employee, employee_id)
        if e:
            e.status = "FAILED"
            db.commit()
        raise HTTPException(status_code=500, detail=str(ex))

# ---------- API: Logs ----------
@app.get("/api/logs/{employee_id}")
def get_logs(employee_id: int, db=Depends(get_db)):
    logs = (
        db.query(AgentLog)
        .filter(AgentLog.employee_id == employee_id)
        .order_by(AgentLog.id.asc())
        .all()
    )

    def _pack(x: AgentLog):
        return {
            "id": x.id,
            "agent": x.agent,
            "input": x.input,
            "steps": x.steps,
            "output": x.output,
            "status": x.status,
            "created_at": x.created_at.isoformat(),
        }

    return list(map(_pack, logs))


# ---------- Dev server entry ----------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=API_HOST,
        port=int(API_PORT),
        log_level=API_LOG_LEVEL,
    )
