import calendar
from expiry_detector_v2 import run_ocr, clean_text, find_expiry_sections, find_month_year, find_month_year_with_suffix, find_numeric_dates, find_compact_expiry_dates, find_year_month_name_day, remove_duplicates, choose_expiry
from teachable_service import predict_medicine
import cv2

GENERIC_NAME_MAP = {
    "Dolo 650": "Paracetamol",
    "Crocin": "Paracetamol",
    "Amoxil": "Amoxicillin"
}


def get_last_day_of_month(year: int, month: int) -> str:
    if not year or not month:
        return None
    _, last_day = calendar.monthrange(year, month)
    return f"{year:04d}-{month:02d}-{last_day:02d}"


def detect_expiry_and_medicine(image_path: str) -> dict:
    # 1. Run Teachable Machine Prediction
    tm_result = predict_medicine(image_path)
    medicine_name = tm_result["medicine_name"]
    confidence = tm_result["confidence"]

    # 2. Run OCR Expiry Detection
    image = cv2.imread(image_path)
    if image is None:
        ocr_text = ""
        final_candidate = None
    else:
        detections = run_ocr(image)
        ocr_text = " ".join(text for text, score in detections if score >= 0.30)
        cleaned = clean_text(ocr_text)
        sections = find_expiry_sections(cleaned)

        candidates = []
        for section in sections:
            find_month_year(section, candidates, 100)
            find_month_year_with_suffix(section, candidates, 110)
            find_numeric_dates(section, candidates, 100)
            find_compact_expiry_dates(section, candidates)

        find_month_year(cleaned, candidates, 20)
        find_month_year_with_suffix(cleaned, candidates, 30)
        find_numeric_dates(cleaned, candidates, 20)
        find_year_month_name_day(cleaned, candidates, 40)
        find_compact_expiry_dates(cleaned, candidates)

        unique_candidates = remove_duplicates(candidates)
        final_candidate = choose_expiry(unique_candidates)

    # 3. Process Dates
    expiry_date_str = None
    if final_candidate:
        expiry_date_str = get_last_day_of_month(final_candidate["year"], final_candidate["month"])

    medicine_found = confidence > 0.5
    generic_name = GENERIC_NAME_MAP.get(medicine_name, "Unknown")

    # 4. Return Output Matching Schema (Without internal IDs)
    return {
        "medicine_found": medicine_found,
        "confidence": confidence,
        "medicine": {
            "name": medicine_name,
            "generic_name": generic_name
        },
        "expiry_date": expiry_date_str,
        "ocr_text": ocr_text,
        "requires_confirmation": confidence < 0.85 or not bool(expiry_date_str)
    }