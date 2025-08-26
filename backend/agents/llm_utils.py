# backend/agents/llm_utils.py
import os, httpx, json, re
from typing import Dict, Any, Optional
from settings import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL, LLM_TEMPERATURE, LLM_TIMEOUT

def have_llm() -> bool:
    return bool(OPENAI_API_KEY)

async def _chat_json(prompt: str) -> Dict[str, Any]:
    """Call an OpenAI-compatible chat API and force a JSON object response."""
    if not have_llm():
        return {"_notes": "LLM not configured"}
    url = (OPENAI_BASE_URL or "https://api.openai.com/v1") + "/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    body = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": LLM_TEMPERATURE,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except Exception:
            return {"_notes": "non-json-response"}

def _redact_email(s: str) -> str:
    """เบลออีเมลเล็กน้อย เพื่อลด PII ใน prompt"""
    return re.sub(r'([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[^,\s]+)', r'\1***\2', s)

# === 1) ใช้ใน Validator ===
async def llm_normalize_employee(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    ตรวจ/ปรับรูปแบบข้อมูลพนักงานให้เข้มขึ้นด้วย LLM
    คืน JSON เฉพาะคีย์: {"corrections": [...], "warnings": [...]}
    หมายเหตุ: ถ้าไม่มีคีย์ LLM จะคืนผล fallback ที่ปลอดภัย
    """
    # fallback เมื่อไม่มีคีย์
    if not have_llm():
        return {
            "corrections": [],
            "warnings": ["LLM not configured; used rule-based fallback."]
        }

    safe = dict(payload)
    if "email" in safe:
        safe["email"] = _redact_email(str(safe["email"]))

    prompt = f"""
You are a strict data normalization assistant for HR onboarding.
Validate and normalize fields: name, email, role, department, start_date (YYYY-MM-DD).
Return ONLY JSON with exactly these keys:
{{
  "corrections": [  // list of patch operations to apply
    // e.g. {{ "field": "role", "from": "ai engineer", "to": "AI Engineer" }}
  ],
  "warnings": [     // free-form notes about potential issues
  ]
}}
Input: {safe}
"""
    result = await _chat_json(prompt)
    # guard rail รูปแบบผลลัพธ์
    corr = result.get("corrections") if isinstance(result, dict) else None
    warn = result.get("warnings") if isinstance(result, dict) else None
    if not isinstance(corr, list): corr = []
    if not isinstance(warn, list): warn = []
    return {"corrections": corr[:20], "warnings": warn[:20]}

# === 2) ใช้ใน Notifier (อีเมลต้อนรับ) ===
async def llm_welcome_email(name: str, role: str, start_date: str) -> str:
    # ถ้าไม่มีคีย์ จะคืนข้อความเทมเพลต
    if not have_llm():
        return f"Welcome {name}! Your role is {role}. Your first day is {start_date}. We’re excited to have you."
    url = (OPENAI_BASE_URL or "https://api.openai.com/v1") + "/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "Write concise, professional corporate email (<=120 words)."},
            {"role": "user", "content": f"Draft a welcome email for {name}, starting as {role} on {start_date}."},
        ],
        "temperature": 0.5,
    }
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()

# === 3) ใช้ใน Scheduler (เวลานัด/รายละเอียดอัตโนมัติ) ===
async def llm_propose_orientation_event(name: str, email: str, start_date: str, role: str, tz: str="Asia/Bangkok") -> Dict[str, Any]:
    """
    ให้ AI เสนอช่วงเวลานัด 1 ชม. ใน business hours 09:00–17:00
    คืน JSON:
    {
      "start": {"dateTime":"YYYY-MM-DDTHH:MM:SS","timeZone": "..."},
      "end":   {"dateTime":"YYYY-MM-DDTHH:MM:SS","timeZone": "..."},
      "location":"...", "description":"..."
    }
    """
    safe_email = _redact_email(email)
    prompt = f"""
You schedule a 1-hour Day-1 orientation for a new hire during 09:00-17:00 {tz}.
Return ONLY JSON:
{{
  "start": {{"dateTime": "YYYY-MM-DDTHH:MM:SS", "timeZone": "{tz}"}},
  "end":   {{"dateTime": "YYYY-MM-DDTHH:MM:SS", "timeZone": "{tz}"}},
  "location": "HQ – Room A",
  "description": "Welcome & IT setup"
}}
Inputs: name="{name}", email="{safe_email}", start_date="{start_date}", role="{role}"
"""
    return await _chat_json(prompt)
