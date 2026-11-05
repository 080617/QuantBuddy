"""QuantBuddy's minimal local read-only web API."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.futu.exceptions import FutuServiceError

from .futu_router import router as futu_router


app = FastAPI(
    title="QuantBuddy Local API",
    version="3A",
    description="Read-only CN simulated-account integration for the local QuantBuddy frontend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Accept", "Content-Type"],
)


@app.exception_handler(FutuServiceError)
def handle_futu_service_error(_: Request, __: FutuServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "code": "FUTU_SERVICE_UNAVAILABLE",
                "message": "Futu read service is currently unavailable.",
            }
        },
    )


app.include_router(futu_router)

