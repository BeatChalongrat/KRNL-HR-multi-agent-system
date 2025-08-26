import os

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "krnl_onboarding")
POSTGRES_USER = os.getenv("POSTGRES_USER", "krnl_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "krnl_pass")

DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8080"))
API_LOG_LEVEL = os.getenv("API_LOG_LEVEL", "info")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")

GOOGLE_CALENDAR_CREDENTIALS_JSON = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_JSON")

SIMULATE_INTEGRATIONS = os.getenv("SIMULATE_INTEGRATIONS", "true").lower() == "true"
# === LLM settings (needed by agents.llm_utils) ===
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

# === Defaults for scheduling/email content ===
DEFAULT_TZ = os.getenv("DEFAULT_TZ", "Asia/Bangkok")
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "HQ - Room A")
