from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func
from settings import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)
    department = Column(String, nullable=True)
    start_date = Column(Date, nullable=False)
    status = Column(String, default="PENDING")
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    account = relationship("Account", back_populates="employee", uselist=False, cascade="all, delete-orphan")
    events = relationship("CalendarEvent", back_populates="employee", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="employee", cascade="all, delete-orphan")
    logs = relationship("AgentLog", back_populates="employee", cascade="all, delete-orphan")

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    username = Column(String, nullable=False, unique=True)
    temp_password = Column(String, nullable=False)
    permissions = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    employee = relationship("Employee", back_populates="account")

class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    event_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    employee = relationship("Employee", back_populates="events")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    channel = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    sent_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    employee = relationship("Employee", back_populates="notifications")

class AgentLog(Base):
    __tablename__ = "agent_logs"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    agent = Column(String, nullable=False)
    input = Column(JSON, nullable=True)
    steps = Column(JSON, nullable=True)
    output = Column(JSON, nullable=True)
    status = Column(String, default="OK")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    employee = relationship("Employee", back_populates="logs")

def init_db():
    Base.metadata.create_all(bind=engine)
