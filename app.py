import calendar
import os
import shutil
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Query
from pydantic import BaseModel

import database
from expiry_detector_v2 import detect_expiry_from_image
from teachable_service import predict_medicine

app = FastAPI(title="Curionix Backend")


class ConfirmRequest(BaseModel):
    scan_session_id: str
    user_id: str
    confirmed: bool


def get_last_day_of_month(year: int, month: int) -> int:
    _, last_day = calendar.monthrange(year, month)
    return last_day


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Curionix API"}


# -------------------------------------------------------------
# MEDICINE MASTER ENDPOINTS
# -------------------------------------------------------------
@app.get("/medicines/search")
def search_medicines(query: str = Query("", alias="query")):
    try:
        results = database.search_medicines_in_db(query)
        compact = [
            {
                "medicine_id": item.get("medicine_id"),
                "brand_name": item.get("brand_name"),
            }
            for item in results
        ]
        return {"ok": True, "results": compact}
    except Exception:
        raise HTTPException(status_code=500, detail="Database search error")


@app.get("/medicines/{medicine_id}")
def get_medicine_details(medicine_id: str):
    doc = database.get_medicine_by_id(medicine_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return {"ok": True, "medicine": doc}


# -------------------------------------------------------------
# STAGED SCANNER ENDPOINTS
# -------------------------------------------------------------
@app.post("/scan/medicine")
async def scan_medicine_stage(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        prediction = predict_medicine(temp_path)
        pred_label = prediction["medicine_name"]
        confidence = prediction["confidence"]
        probabilities = prediction.get("probabilities", {})

        if not pred_label or confidence < 0.50:
            return {
                "ok": False,
                "stage": "medicine",
                "code": "MEDICINE_LOW_CONFIDENCE",
                "message": "Could not recognize medicine clearly. Please try again.",
                "retryable": True,
                "debug_prediction": {
                    "predicted_label": pred_label,
                    "confidence": confidence,
                    "probabilities": probabilities,
                },
            }

        master_doc = database.find_medicine_by_label(pred_label)

        if not master_doc:
            return {
                "ok": False,
                "stage": "medicine",
                "code": "MEDICINE_NOT_IN_MASTER",
                "message": (
                    f"Recognized label '{pred_label}' not found in "
                    "Medicine_Master."
                ),
                "retryable": True,
                "debug_prediction": {
                    "predicted_label": pred_label,
                    "confidence": confidence,
                    "probabilities": probabilities,
                },
            }

        session_id = database.create_scan_session(
            {
                "medicine_id": master_doc["medicine_id"],
                "brand_name": master_doc["brand_name"],
                "confidence": round(confidence, 2),
            }
        )

        return {
            "ok": True,
            "stage": "medicine",
            "scan_session_id": session_id,
            "medicine": {
                "medicine_id": master_doc["medicine_id"],
                "brand_name": master_doc["brand_name"],
                "confidence": round(confidence, 2),
            },
            "next_step": "TURN_MEDICINE_OVER",
        }

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/scan/expiry")
async def scan_expiry_stage(
    scan_session_id: str = Form(...),
    file: UploadFile = File(...),
):
    session = database.get_scan_session(scan_session_id)

    if not session:
        return {
            "ok": False,
            "stage": "expiry",
            "code": "SCAN_SESSION_NOT_FOUND",
            "message": "Invalid or expired scan session ID.",
            "retryable": False,
        }

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        expiry_res = detect_expiry_from_image(temp_path)

        if (
            not expiry_res.get("expiry_detected")
            or not expiry_res.get("year")
            or not expiry_res.get("month")
        ):
            return {
                "ok": False,
                "stage": "expiry",
                "code": "EXPIRY_NOT_DETECTED",
                "message": (
                    "Expiry date not found in image. "
                    "Please re-take photo or enter manually."
                ),
                "retryable": True,
            }

        year = int(expiry_res["year"])
        month = int(expiry_res["month"])
        day = get_last_day_of_month(year, month)
        formatted_expiry = f"{year:04d}-{month:02d}-{day:02d}"

        database.update_scan_session_expiry(
            scan_session_id,
            formatted_expiry,
        )

        return {
            "ok": True,
            "stage": "expiry",
            "scan_session_id": scan_session_id,
            "expiry_date": formatted_expiry,
            "next_step": "CONFIRM",
        }

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/scan/confirm")
def confirm_scan_stage(payload: ConfirmRequest):
    session = database.get_scan_session(payload.scan_session_id)

    if not session:
        return {
            "ok": False,
            "stage": "confirm",
            "code": "SCAN_SESSION_NOT_FOUND",
            "message": "Invalid or expired scan session ID.",
            "retryable": False,
        }

    # Idempotency check
    if session.get("status") == "CONFIRMED":
        existing_item = database.medical_cabinet_data.find_one(
            {
                "user_id": payload.user_id,
                "medicine_id": session["medicine"]["medicine_id"],
                "expiry_date": session.get("expiry_date"),
            },
            {"_id": 0},
        )

        cabinet_id = (
            existing_item.get("cabinet_item_id")
            if existing_item
            else "ALREADY_CONFIRMED"
        )

        return {
            "ok": True,
            "stage": "confirm",
            "cabinet_item_id": cabinet_id,
            "message": "Already confirmed.",
        }

    if not payload.confirmed:
        return {
            "ok": False,
            "stage": "confirm",
            "code": "CONFIRMATION_REJECTED",
            "message": "User cancelled scan confirmation.",
            "retryable": False,
        }

    medicine_id = session["medicine"]["medicine_id"]
    expiry_date = session.get("expiry_date")

    if not medicine_id or not expiry_date:
        return {
            "ok": False,
            "stage": "confirm",
            "code": "INCOMPLETE_SCAN",
            "message": "Session missing medicine ID or expiry date.",
            "retryable": False,
        }

    cabinet_item_id = database.create_cabinet_item(
        payload.user_id,
        medicine_id,
        expiry_date,
    )

    database.mark_session_consumed(payload.scan_session_id)

    return {
        "ok": True,
        "stage": "confirm",
        "cabinet_item_id": cabinet_item_id,
        "message": "Item added to cabinet successfully.",
    }
