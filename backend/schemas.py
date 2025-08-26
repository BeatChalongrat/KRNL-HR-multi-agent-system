from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Any
from datetime import date

class EmployeeCreate(BaseModel):
    name: str = Field(..., examples=["Ada Lovelace"])
    email: EmailStr = Field(..., examples=["ada@example.com"])
    role: str = Field(..., examples=["AI Engineer"])
    start_date: date
    department: Optional[str] = Field(None, examples=["R&D"])

class EmployeeOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    start_date: date
    department: Optional[str]
    status: str
    class Config:
        from_attributes = True

class LogOut(BaseModel):
    id: int
    agent: str
    input: Any
    steps: Any
    output: Any
    status: str
    class Config:
        from_attributes = True

class RunResult(BaseModel):
    employee_id: int
    trace_ids: List[int]
