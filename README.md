# AI Powered Loan Processing Backend System

## Overview

This project implements a backend loan processing system that includes:

- A **scoring engine** for evaluating loan applications
- A **state machine** enforcing application lifecycle transitions
- A **disbursement orchestration layer**
- A **webhook handler** for payment confirmations
- **duplicate detection and idempotency safeguards**
- **admin review endpoints**

The system is implemented using **Python, FastAPI, and SQLite** and focuses strictly on backend orchestration and decision logic.

---

# Tech Stack

- Python
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- YAML configuration

The system uses **configuration-driven scoring rules and thresholds** rather than hardcoded logic.

---

# Project Structure

AI-Powered-Loan-Application-Processor-Backend
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│
│   ├── models/
│   │   ├── application.py
│   │   ├── audit.py
│
│   ├── schemas/
│   │   ├── application_schema.py
│   │   ├── webhook_schema.py
│
│   ├── services/
│   │   ├── scoring_engine.py
│   │   ├── state_machine.py
│   │   ├── disbursement_service.py
│   │   ├── duplicate_service.py
│
│   ├── routes/
│   │   ├── application_routes.py
│   │   ├── webhook_routes.py
│   │   ├── admin_routes.py
│
│   ├── errors/
│   │   ├── custom_errors.py
│
│   └── utils/
│       ├── idempotency.py
│       ├── time_utils.py
│
├── scripts/
│   └── simulate_disbursement.py
│
├── config.yaml
├── README.md
└── requirements.txt


The architecture separates **domain logic, infrastructure, and API layers** to keep the system modular and maintainable.

---

# Setup Instructions

Create a virtual environment and install dependencies.

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt


# Start the API server.
uvicorn app.main:app --reload

# The API will run locally at:
http://127.0.0.1:8000

