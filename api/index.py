"""
Lisans dogrulama API'si (FastAPI + Supabase)

Ortam degiskenleri:
    SUPABASE_URL          -> https://xxxx.supabase.co
    SUPABASE_SERVICE_KEY  -> service_role anahtari (SADECE sunucuda!)

Vercel serverless entry point: api/index.py
"""

import os

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import Client, create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

app = FastAPI(title="License API")


class ValidateRequest(BaseModel):
    license_key: str = Field(..., min_length=1, max_length=128)
    device_id: str = Field(..., min_length=1, max_length=256)


class ValidateResponse(BaseModel):
    valid: bool
    reason: str


def _do_validate(license_key: str, device_id: str) -> ValidateResponse:
    """Shared logic: calls Supabase RPC and returns a ValidateResponse."""
    try:
        result = supabase.rpc(
            "validate_license",
            {
                "p_license_key": license_key.strip(),
                "p_device_id": device_id.strip(),
            },
        ).execute()
    except Exception:
        raise HTTPException(status_code=503, detail="License service unavailable")

    data = result.data or {}
    return ValidateResponse(
        valid=bool(data.get("valid", False)),
        reason=data.get("reason", "unknown_error"),
    )


# ---------------------------------------------------------------
# GET /validate_license?license_key=...&hwid=...
# (URL format used by the client app)
# ---------------------------------------------------------------
@app.get("/validate_license", response_model=ValidateResponse)
def validate_license_get(
    license_key: str = Query(..., min_length=1, max_length=128),
    hwid: str = Query(..., min_length=1, max_length=256),
) -> ValidateResponse:
    return _do_validate(license_key, hwid)


# ---------------------------------------------------------------
# POST /validate  (JSON body – kept for backward compatibility)
# ---------------------------------------------------------------
@app.post("/validate", response_model=ValidateResponse)
def validate_license_post(body: ValidateRequest) -> ValidateResponse:
    return _do_validate(body.license_key, body.device_id)


@app.get("/")
def root():
    return {"status": "ok", "message": "License API is running"}
