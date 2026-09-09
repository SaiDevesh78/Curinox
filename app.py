import calendar
import os
import shutil
import tempfile

from fastapi import FastAPI, File, UploadFile

from expiry_detector_v2 import detect_expiry_from_image
from teachable_service import predict_medicine

app = FastAPI(title="Curionix Backend")


def get_last_day_of_month(year: int, month: int) -> int:
    _, last_day = calendar.monthrange(year, month)
    return last_day


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Curionix API"}


# -------------------------------------------------------------
# SCANNER ENDPOINTS
# Stateless: each call runs inference on the uploaded image and
# returns the raw result directly. No database, no session
# tracking, nothing persisted.
# -------------------------------------------------------------
@app.post("/scan/medicine")
async def scan_medicine(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        prediction = predict_medicine(temp_path)
        return {
            "ok": bool(prediction["medicine_name"]),
            "medicine_name": prediction["medicine_name"],
            "confidence": prediction["confidence"],
            "probabilities": prediction.get("probabilities", {}),
        }
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/scan/expiry")
async def scan_expiry(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        result = detect_expiry_from_image(temp_path)

        expiry_date = None
        if result.get("expiry_detected") and result.get("year") and result.get("month"):
            year = int(result["year"])
            month = int(result["month"])
            day = get_last_day_of_month(year, month)
            expiry_date = f"{year:04d}-{month:02d}-{day:02d}"

        return {
            "ok": expiry_date is not None,
            "expiry_date": expiry_date,
            "month": result.get("month"),
            "year": result.get("year"),
            "source": result.get("source"),
        }
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
