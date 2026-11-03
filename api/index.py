"""
Lisans dogrulama API'si (FastAPI + Supabase)
"""

import os
from datetime import datetime
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


@app.get("/_debug_inspect")
def debug_inspect():
    out = {}
    for tbl in ["licenses", "license", "devices", "user_licenses"]:
        try:
            res = supabase.table(tbl).select("*").limit(5).execute()
            out[tbl] = {"status": "found", "data": res.data}
        except Exception as e:
            out[tbl] = {"status": "error", "error": str(e)}
    return out


def _do_validate(license_key: str, device_id: str) -> ValidateResponse:
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


@app.get("/validate_license", response_model=ValidateResponse)
def validate_license_get(
    license_key: str = Query(..., min_length=1, max_length=128),
    hwid: str = Query(..., min_length=1, max_length=256),
) -> ValidateResponse:
    return _do_validate(license_key, hwid)


@app.post("/validate", response_model=ValidateResponse)
def validate_license_post(body: ValidateRequest) -> ValidateResponse:
    return _do_validate(body.license_key, body.device_id)


@app.get("/")
def root():
    return {"status": "ok", "message": "License API is running"}