from fastapi import APIRouter, UploadFile, File
import os
import shutil

from expiry_service import detect_expiry
from database import save_scan, get_all_scans


router = APIRouter()

UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.post("/scan")
async def scan(image: UploadFile = File(...)):

    # --------------------------------------------------------
    # SAVE IMAGE
    # --------------------------------------------------------

    filepath = os.path.join(
        UPLOAD_FOLDER,
        image.filename
    )

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(
            image.file,
            buffer
        )

    print()
    print("Image saved:", filepath)

    # --------------------------------------------------------
    # RUN EXPIRY DETECTOR
    # --------------------------------------------------------

    expiry_result = detect_expiry(filepath)

    # --------------------------------------------------------
    # SAVE RESULT TO DATABASE
    # --------------------------------------------------------

    scan_id = save_scan(
        filename=image.filename,
        expiry=expiry_result.get("expiry"),
        month=expiry_result.get("month"),
        year=expiry_result.get("year")
    )

    # --------------------------------------------------------
    # RETURN RESULT
    # --------------------------------------------------------

    return {
        "message": "Image scanned successfully",
        "id": scan_id,
        "filename": image.filename,
        **expiry_result
    }


@router.get("/scans")
def scans():

    return {
        "scans": get_all_scans()
    }