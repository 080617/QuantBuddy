# QuantBuddy Futu Service

This backend package wraps the previously verified Futu smoke-test operations behind reusable, typed services. It is intentionally restricted to **China A-share (`CN`) simulated (`SIMULATE`) trading**.

## Safety boundary

- Real trading is rejected during configuration and again before every write.
- Simulated order writes are disabled by default.
- No login password, trading unlock password, token, or real account details are accepted or stored.
- Account and order identifiers must be masked in normal application output.
- Importing the package does not connect to FutuOpenD.
- The default smoke command is read-only and never places or cancels orders.

## Prerequisites

1. Install, start, and sign in to FutuOpenD.
2. Keep its API listener at `127.0.0.1:11111`, or set `FUTU_HOST` and `FUTU_PORT`.
3. Ensure exactly one active CN simulated account is available, or set `FUTU_ACCOUNT_ID` at runtime.

## Python environment

From the repository root in PowerShell:

```powershell
python -m venv .venv-futu
.\.venv-futu\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Copy the documented names from `backend/.env.example` into your own local environment. Do not commit a real `.env` file.

## Validation and tests

Syntax check and isolated unit tests do not require OpenD:

```powershell
python -m compileall -q backend\futu backend\tests
python -m unittest discover -s backend\tests -p "test_*.py" -v
```

Run the unified read-only OpenD smoke test explicitly:

```powershell
python -m backend.futu.smoke_readonly
```

It performs a health check, account selection, funds, positions, one quote snapshot, and current/historical order reads. It cannot submit or cancel an order.

## Local read-only Web API

Install the backend requirements, keep FutuOpenD signed in, and start the API from the repository root:

```powershell
.\.venv-futu\Scripts\python.exe -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

The API exposes only five `GET` endpoints under `/api/futu`: `status`, `account`, `positions`, `orders`, and `portfolio`. It is restricted to the existing CN simulated-account services, masks account and order identifiers, and allows browser requests only from `http://localhost:3000`. No order placement, cancellation, modification, Canary, or execution route is exposed.

The frontend reads the API base URL from `NEXT_PUBLIC_BACKEND_URL` (default local value: `http://127.0.0.1:8000`).

## Explicit simulated order enablement

The service defaults to `FUTU_ENABLE_SIMULATED_ORDERS=false`. An operator must explicitly set it to `true` for a separately invoked simulated-order workflow. Safety checks still enforce CN, SIMULATE, active account, code format, lot size, positive price/quantity, current quote refresh, maximum tradable quantity, and the configured single-order amount limit.

There is no parameter that switches to REAL, and this package does not implement real-trading unlock.

## Current scope

The Futu service is not connected to Qlib signals, the Next.js frontend, automatic execution, or a simulated-trading UI. Existing scripts in `backend/futu_smoke_test` are retained as manual integration evidence.
