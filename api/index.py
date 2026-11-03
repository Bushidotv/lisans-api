"""
Lisans dogrulama API'si (FastAPI + Supabase)

Ortam degiskenleri:
    SUPABASE_URL          -> https://xxxx.supabase.co
    SUPABASE_SERVICE_KEY  -> service_role anahtari (SADECE sunucuda!)

Vercel serverless entry point: api/index.py
"""

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import Client, create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

app = FastAPI(title="License API")


class ValidateRequest(BaseModel):
    license_key: str = Field(..., min_length=1, max_length=128)
    device_id: Optional[str] = Field(None, min_length=1, max_length=256)
    hwid: Optional[str] = Field(None, min_length=1, max_length=256)


class ValidateResponse(BaseModel):
    valid: bool
    reason: str


def _do_validate(license_key: str, device_id: str) -> ValidateResponse:
    """
    Validates a license key and auto-binds device HWID based on max_devices:
    1. If license does not exist or status is not active -> invalid_license
    2. If license has expired -> license_expired
    3. If device_id is already in device_ids -> valid=True, reason="device_registered"
    4. If device_id is not in device_ids:
       - if count(device_ids) < max_devices:
           append device_id to device_ids in Supabase
           return valid=True, reason="device_bound_successfully"
       - if count(device_ids) >= max_devices:
           return valid=False, reason="device_limit_reached"
    """
    clean_key = license_key.strip()
    clean_hwid = device_id.strip()

    try:
        # Fetch license record from Supabase
        response = (
            supabase.table("licenses")
            .select("*")
            .eq("license_key", clean_key)
            .limit(1)
            .execute()
        )
    except Exception as e:
        print(f"Supabase connection error: {e}")
        raise HTTPException(status_code=503, detail="License service unavailable")

    rows = response.data or []
    if not rows:
        return ValidateResponse(valid=False, reason="invalid_license")

    license_row = rows[0]

    # 1. Check license status (must be 'active')
    status = (license_row.get("status") or "").strip().lower()
    if status and status != "active":
        return ValidateResponse(valid=False, reason="invalid_license")

    # 2. Check expiration date if present
    expire_date_str = license_row.get("expire_date")
    if expire_date_str:
        try:
            exp_dt = datetime.fromisoformat(expire_date_str.replace("Z", "+00:00"))
            now_utc = datetime.now(timezone.utc)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if now_utc > exp_dt:
                return ValidateResponse(valid=False, reason="license_expired")
        except Exception as e:
            print(f"Error parsing expire_date: {e}")

    # 3. Handle device IDs array
    raw_devices = license_row.get("device_ids")
    if raw_devices is None:
        device_ids = []
    elif isinstance(raw_devices, list):
        device_ids = [str(d).strip() for d in raw_devices if d]
    else:
        device_ids = [str(raw_devices).strip()]

    max_devices = license_row.get("max_devices")
    if max_devices is None or max_devices <= 0:
        max_devices = 1

    # 4. Check if device is already registered
    if clean_hwid in device_ids:
        return ValidateResponse(valid=True, reason="device_registered")

    # 5. Check device limit and auto-bind
    if len(device_ids) < max_devices:
        new_device_ids = list(device_ids) + [clean_hwid]
        try:
            supabase.table("licenses").update({"device_ids": new_device_ids}).eq(
                "id", license_row["id"]
            ).execute()
        except Exception as e:
            print(f"Supabase update error: {e}")
            raise HTTPException(status_code=503, detail="License service unavailable")

        return ValidateResponse(valid=True, reason="device_bound_successfully")
    else:
        return ValidateResponse(valid=False, reason="device_limit_reached")


# ---------------------------------------------------------------
# GET /validate_license?license_key=...&hwid=...
# (Also accepts ?device_id=...)
# ---------------------------------------------------------------
@app.get("/validate_license", response_model=ValidateResponse)
def validate_license_get(
    license_key: str = Query(..., min_length=1, max_length=128),
    hwid: Optional[str] = Query(None, min_length=1, max_length=256),
    device_id: Optional[str] = Query(None, min_length=1, max_length=256),
) -> ValidateResponse:
    dev = hwid or device_id
    if not dev:
        raise HTTPException(
            status_code=422,
            detail="Missing device identifier: query parameter 'hwid' or 'device_id' is required",
        )
    return _do_validate(license_key, dev)


# ---------------------------------------------------------------
# GET /validate?license_key=...&hwid=...
# ---------------------------------------------------------------
@app.get("/validate", response_model=ValidateResponse)
def validate_get(
    license_key: str = Query(..., min_length=1, max_length=128),
    hwid: Optional[str] = Query(None, min_length=1, max_length=256),
    device_id: Optional[str] = Query(None, min_length=1, max_length=256),
) -> ValidateResponse:
    dev = hwid or device_id
    if not dev:
        raise HTTPException(
            status_code=422,
            detail="Missing device identifier: query parameter 'hwid' or 'device_id' is required",
        )
    return _do_validate(license_key, dev)


# ---------------------------------------------------------------
# POST /validate (JSON body)
# ---------------------------------------------------------------
@app.post("/validate", response_model=ValidateResponse)
def validate_license_post(body: ValidateRequest) -> ValidateResponse:
    dev = body.hwid or body.device_id
    if not dev:
        raise HTTPException(
            status_code=422,
            detail="Missing device identifier: 'hwid' or 'device_id' must be provided in body",
        )
    return _do_validate(body.license_key, dev)


# ---------------------------------------------------------------
# POST /validate_license (JSON body)
# ---------------------------------------------------------------
@app.post("/validate_license", response_model=ValidateResponse)
def validate_license_post_alias(body: ValidateRequest) -> ValidateResponse:
    dev = body.hwid or body.device_id
    if not dev:
        raise HTTPException(
            status_code=422,
            detail="Missing device identifier: 'hwid' or 'device_id' must be provided in body",
        )
    return _do_validate(body.license_key, dev)


@app.get("/")
def root():
    return {"status": "ok", "message": "License API is running"}
