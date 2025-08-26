# KRNL Onboarding – Enterprise Edition

Enterprise-style multi-agent onboarding:
- FastAPI + Postgres + Docker Compose
- Agents: Validator, Account (A2A→Scheduler), Scheduler, Notifier
- Optional LLM normalization & welcome email
- Verifiable logs & dashboard
- MCP manifest for Scheduler

## Run
1) Copy `.env.example` to `.env`
2) `docker compose up --build`
3) Open `http://localhost:8080`

## API
- POST `/api/employees`
- POST `/api/employees/upload_csv`
- GET  `/api/employees`
- GET  `/api/employees/{id}`
- POST `/api/run/{id}`
- GET  `/api/logs/{id}`

## Tests
- `docker compose exec api pytest -q`
