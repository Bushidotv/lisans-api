"""
Lisans doğrulama API'si (FastAPI + Supabase)

Kurulum:
    pip install fastapi uvicorn supabase

Ortam değişkenleri:
    SUPABASE_URL          -> https://xxxx.supabase.co
    SUPABASE_SERVICE_KEY  -> service_role anahtarı (SADECE sunucuda, istemciye asla verme!)

Çalıştırma:
    uvicorn main:app --host 0.0.0.0 --port 8000

Test:
    curl -X POST http://localhost:8000/validate \
         -H "Content-Type: application/json" \
         -d '{"license_key": "ABCD-1234-EFGH-5678", "device_id": "device-001"}'
"""

import os

from fastapi import FastAPI, HTTPException
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
    valid: bool    # True / False
    reason: str    # license_not_found | license_expired | device_limit_reached
                   # device_already_registered | device_registered


@app.post("/validate", response_model=ValidateResponse)
def validate_license(body: ValidateRequest) -> ValidateResponse:
    # Tüm kontroller (kod var mı, süresi geçmiş mi, cihaz kayıtlı mı / limit dolu mu)
    # veritabanındaki validate_license fonksiyonunda tek bir kilitli işlemde yapılır.
    try:
        result = supabase.rpc(
            "validate_license",
            {
                "p_license_key": body.license_key.strip(),
                "p_device_id": body.device_id.strip(),
            },
        ).execute()
    except Exception:
        # Veritabanına ulaşılamazsa "geçerli" dönme; hata ver.
        raise HTTPException(status_code=503, detail="License service unavailable")

    data = result.data or {}
    return ValidateResponse(
        valid=bool(data.get("valid", False)),
        reason=data.get("reason", "unknown_error"),
    )
