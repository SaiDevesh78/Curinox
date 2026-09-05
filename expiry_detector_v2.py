import cv2
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

# ============================================================
# OPTIONAL DATABASE (used only when this file is run directly)
# ============================================================
try:
    import database
except ImportError:
    database = None

# ============================================================
# RAPIDOCR
# ============================================================
try:
    from rapidocr import RapidOCR
except ImportError:
    from rapidocr_onnxruntime import RapidOCR

# ============================================================
# SETTINGS
# ============================================================
INPUT_IMAGE = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "uploads/medi2_upscaled.png"
)

OUTPUT_DIR = "uploads/expiry_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Keep the working V6-style initialization.
ocr = RapidOCR()

# ============================================================
# MONTHS
# ============================================================
MONTHS = {
    "JAN": 1,
    "JANUARY": 1,
    "FEB": 2,
    "FEBRUARY": 2,
    "MAR": 3,
    "MARCH": 3,
    "APR": 4,
    "APRIL": 4,
    "MAY": 5,
    "JUN": 6,
    "JUNE": 6,
    "JUL": 7,
    "JULY": 7,
    "AUG": 8,
    "AUGUST": 8,
    "SEP": 9,
    "SEPT": 9,
    "SEPTEMBER": 9,
    "OCT": 10,
    "OCTOBER": 10,
    "NOV": 11,
    "NOVEMBER": 11,
    "DEC": 12,
    "DECEMBER": 12,
}

MONTH_ALTERNATION = (
    r"JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|"
    r"SEPTEMBER|DECEMBER|JAN|FEB|MAR|APR|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC"
)

# ============================================================
# OCR RESULT NORMALIZATION
# ============================================================
def _score_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def run_ocr(img) -> List[Any]:
    """Return [(text, score), ...] for both older and newer RapidOCR APIs."""
    try:
        result = ocr(img)
    except Exception:
        return []

    if result is None:
        return []

    # Newer RapidOCR result object.
    txts = getattr(result, "txts", None)
    scores = getattr(result, "scores", None)
    if txts is not None:
        output = []
        for i, text in enumerate(txts):
            score = scores[i] if scores is not None and i < len(scores) else 1.0
            if text is not None and str(text).strip():
                output.append((str(text), _score_value(score)))
        return output

    # Some versions expose OCRResult as a dict-like object.
    if isinstance(result, dict):
        txts = result.get("txts") or result.get("text") or result.get("texts") or []
        scores = result.get("scores") or result.get("score") or []
        if isinstance(txts, str):
            txts = [txts]
        output = []
        for i, text in enumerate(txts):
            score = scores[i] if isinstance(scores, (list, tuple)) and i < len(scores) else 1.0
            if text is not None and str(text).strip():
                output.append((str(text), _score_value(score)))
        if output:
            return output

    # Older RapidOCR API: (boxes, txts, scores)
    if isinstance(result, (tuple, list)) and len(result) >= 3:
        txts = result[1]
        scores = result[2]
        output = []
        try:
            for i, item in enumerate(txts):
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    text = item[0]
                    score = item[1]
                else:
                    text = item
                    score = scores[i] if i < len(scores) else 1.0
                if text is not None and str(text).strip():
                    output.append((str(text), _score_value(score)))
        except Exception:
            return []
        return output

    # Rare list-of-(text, score) style.
    if isinstance(result, (tuple, list)):
        output = []
        for item in result:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                text, score = item[0], item[1]
                if isinstance(text, str) and text.strip():
                    output.append((text, _score_value(score)))
        return output

    return []


# ============================================================
# TEXT CLEANING
# ============================================================
def clean_text(text: str) -> str:
    text = str(text or "").upper()

    # Normalize common OCR punctuation variants.
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("−", "-")
    text = text.replace("／", "/")
    text = text.replace("．", ".")

    # OCR often inserts spaces inside labels.
    text = re.sub(r"E\s*X\s*P\s*I\s*R\s*Y", "EXPIRY", text)
    text = re.sub(r"E\s*X\s*P", "EXP", text)

    # Normalize whitespace.
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================================================
# EXPIRY KEYWORDS / SECTIONS
# ============================================================
EXPIRY_KEYWORD_PATTERN = re.compile(
    r"\b(?:EXP(?:IRY)?|EXPIRATION)\b",
    re.IGNORECASE,
)


def has_expiry_keyword(text: str) -> bool:
    return bool(EXPIRY_KEYWORD_PATTERN.search(text))


def find_expiry_sections(text: str) -> List[str]:
    """Return text surrounding every EXP/EXPIRY occurrence."""
    sections: List[str] = []

    for match in EXPIRY_KEYWORD_PATTERN.finditer(text):
        start = max(0, match.start() - 20)
        end = min(len(text), match.end() + 100)
        section = text[start:end].strip()
        if section:
            sections.append(section)

    return sections


# ============================================================
# YEAR NORMALIZATION
# ============================================================
def normalize_year(value: Any) -> Optional[int]:
    try:
        value = int(str(value))
    except (TypeError, ValueError):
        return None

    if 1900 <= value <= 2100:
        return value

    if 0 <= value <= 99:
        return 2000 + value

    return None


# ============================================================
# ADD CANDIDATE
# ============================================================
def add_candidate(
    candidates: List[Dict[str, Any]],
    month: int,
    year: Optional[int],
    raw: str,
    source: str,
    priority: int = 0,
) -> None:
    if year is None:
        return
    if not 1 <= int(month) <= 12:
        return

    candidates.append(
        {
            "month": int(month),
            "year": int(year),
            "raw": str(raw).strip(),
            "source": source,
            "priority": int(priority),
        }
    )


# ============================================================
# MONTH + YEAR DETECTOR
# ============================================================
def find_month_year(
    text: str,
    candidates: List[Dict[str, Any]],
    priority: int = 0,
) -> None:
    month_pattern = rf"({MONTH_ALTERNATION})"

    # --------------------------------------------------------
    # MONTH + 4 DIGIT YEAR
    # SEP 2019 / SEP.2019 / SEP-2019 / SEP/2019
    # --------------------------------------------------------
    pattern_4 = (
        r"(?<!\d)"
        + month_pattern
        + r"\s*[\.\-/]?\s*"
        + r"(19\d{2}|20\d{2})"
    )

    for match in re.finditer(pattern_4, text, re.IGNORECASE):
        month_name = match.group(1).upper()
        year = normalize_year(match.group(2))
        add_candidate(
            candidates,
            MONTHS[month_name],
            year,
            match.group(0),
            "MONTH_YEAR",
            priority,
        )

    # --------------------------------------------------------
    # MONTH + 2 DIGIT YEAR
    # SEP19 / SEP.19 / SEP-19 / SEP/19
    # --------------------------------------------------------
    pattern_2 = (
        r"(?<!\d)"
        + month_pattern
        + r"\s*[\.\-/]?\s*"
        + r"(\d{2})(?!\d)"
    )

    for match in re.finditer(pattern_2, text, re.IGNORECASE):
        month_name = match.group(1).upper()
        year = normalize_year(match.group(2))
        add_candidate(
            candidates,
            MONTHS[month_name],
            year,
            match.group(0),
            "MONTH_YEAR",
            priority,
        )


# ============================================================
# SPECIAL MONTH + YEAR SUFFIX
# SEP.19M / SEP19M / SEP 19 M
# ============================================================
def find_month_year_with_suffix(
    text: str,
    candidates: List[Dict[str, Any]],
    priority: int = 0,
) -> None:
    month_pattern = rf"({MONTH_ALTERNATION})"

    pattern = (
        r"(?<!\d)"
        + month_pattern
        + r"\s*[\.\-/]?\s*"
        + r"(\d{2,4})"
        + r"\s*[A-Z]?"
    )

    for match in re.finditer(pattern, text, re.IGNORECASE):
        month_name = match.group(1).upper()
        year = normalize_year(match.group(2))
        add_candidate(
            candidates,
            MONTHS[month_name],
            year,
            match.group(0),
            "MONTH_YEAR_SUFFIX",
            priority + 10,
        )


# ============================================================
# NUMERIC DATE DETECTOR
# ============================================================
def find_numeric_dates(
    text: str,
    candidates: List[Dict[str, Any]],
    priority: int = 0,
) -> None:
    # --------------------------------------------------------
    # YYYY/MM/DD or YYYY-MM-DD
    # Example: 2025/04/20 -> 04/2025
    # This is checked first.
    # --------------------------------------------------------
    pattern_year_first = (
        r"(?<!\d)"
        r"(19\d{2}|20\d{2})"
        r"\s*[\-/\.]\s*"
        r"(0?[1-9]|1[0-2])"
        r"\s*[\-/\.]\s*"
        r"(0?[1-9]|[12]\d|3[01])"
        r"(?!\d)"
    )

    for match in re.finditer(pattern_year_first, text):
        year = normalize_year(match.group(1))
        month = int(match.group(2))
        add_candidate(
            candidates,
            month,
            year,
            match.group(0),
            "YEAR_FIRST",
            priority + 20,
        )

    # --------------------------------------------------------
    # MM/YYYY
    # --------------------------------------------------------
    pattern_mm_yyyy = (
        r"(?<!\d)"
        r"(0?[1-9]|1[0-2])"
        r"\s*[\-/\.]\s*"
        r"(19\d{2}|20\d{2})"
        r"(?!\d)"
    )

    for match in re.finditer(pattern_mm_yyyy, text):
        month = int(match.group(1))
        year = normalize_year(match.group(2))
        add_candidate(
            candidates,
            month,
            year,
            match.group(0),
            "MM_YYYY",
            priority,
        )

    # --------------------------------------------------------
    # MM/YY
    # --------------------------------------------------------
    pattern_mm_yy = (
        r"(?<!\d)"
        r"(0?[1-9]|1[0-2])"
        r"\s*[\-/\.]\s*"
        r"(\d{2})"
        r"(?!\d)"
    )

    for match in re.finditer(pattern_mm_yy, text):
        month = int(match.group(1))
        year = normalize_year(match.group(2))
        add_candidate(
            candidates,
            month,
            year,
            match.group(0),
            "MM_YY",
            priority,
        )

    # --------------------------------------------------------
    # THREE-PART DATE
    # Handles DD/MM/YYYY, MM/DD/YYYY, etc.
    # IMPORTANT REQUIREMENT:
    # 04/12/2026 -> 12/2026
    # --------------------------------------------------------
    pattern_three = (
        r"(?<!\d)"
        r"(\d{1,2})"
        r"\s*[\-/\.]\s*"
        r"(\d{1,2})"
        r"\s*[\-/\.]\s*"
        r"(\d{2}|\d{4})"
        r"(?!\d)"
    )

    for match in re.finditer(pattern_three, text):
        first = int(match.group(1))
        second = int(match.group(2))
        year = normalize_year(match.group(3))

        if year is None:
            continue

        # DD/MM/YYYY: when second is a valid month.
        # This intentionally makes 04/12/2026 -> 12/2026.
        if 1 <= first <= 31 and 1 <= second <= 12:
            add_candidate(
                candidates,
                second,
                year,
                match.group(0),
                "DAY_MONTH_YEAR",
                priority + 5,
            )
            continue

        # MM/DD/YYYY: second > 12 means it cannot be a month.
        if 1 <= first <= 12 and 13 <= second <= 31:
            add_candidate(
                candidates,
                first,
                year,
                match.group(0),
                "MONTH_DAY_YEAR",
                priority + 5,
            )
            continue

        # OCR fallback.
        # Example: 05/98/08
        # Preserve the old V6-style fallback: first valid value is
        # treated as month and the second value as a year when possible.
        if 1 <= first <= 12:
            fallback_year = normalize_year(second)
            if fallback_year is not None:
                add_candidate(
                    candidates,
                    first,
                    fallback_year,
                    match.group(0),
                    "OCR_FALLBACK",
                    priority - 10,
                )


# ============================================================
# COMPACT EXPIRY DATE
# EXPIRYDATE05/98/08
# ============================================================
def find_compact_expiry_dates(
    text: str,
    candidates: List[Dict[str, Any]],
    priority: int = 0,
) -> None:
    pattern = re.compile(
        r"(?:EXPIRY\s*DATE|EXP\s*DATE|EXPIRY|EXP)"
        r"\s*[:\.-]?\s*"
        r"(\d{1,2})"
        r"\s*[\-/\.]\s*"
        r"(\d{1,2})"
        r"\s*[\-/\.]\s*"
        r"(\d{2}|\d{4})",
        re.IGNORECASE,
    )

    for match in pattern.finditer(text):
        first = int(match.group(1))
        second = int(match.group(2))
        year_value = match.group(3)

        year = normalize_year(year_value)
        if year is not None and 1 <= first <= 31 and 1 <= second <= 12:
            # DD/MM/YYYY -> month is the middle component.
            add_candidate(
                candidates,
                second,
                year,
                match.group(0),
                "COMPACT_EXPIRY",
                priority + 100,
            )
            continue

        if year is not None and 1 <= first <= 12 and 13 <= second <= 31:
            # MM/DD/YYYY -> month is the first component.
            add_candidate(
                candidates,
                first,
                year,
                match.group(0),
                "COMPACT_EXPIRY",
                priority + 100,
            )
            continue

        # OCR fallback for cases like EXPIRYDATE05/98/08.
        fallback_year = normalize_year(second)
        if 1 <= first <= 12 and fallback_year is not None:
            add_candidate(
                candidates,
                first,
                fallback_year,
                match.group(0),
                "COMPACT_EXPIRY_FALLBACK",
                priority + 90,
            )


# ============================================================
# SPECIAL YEAR + MONTH NAME + DAY
# Example: 2022MAR23 -> 03/2022
# ============================================================
def find_year_month_name_day(
    text: str,
    candidates: List[Dict[str, Any]],
    priority: int = 0,
) -> None:
    month_pattern = rf"({MONTH_ALTERNATION})"

    pattern = (
        r"(?<!\d)"
        r"(19\d{2}|20\d{2})"
        + month_pattern
        + r"(0?[1-9]|[12]\d|3[01])"
        r"(?!\d)"
    )

    for match in re.finditer(pattern, text, re.IGNORECASE):
        year = normalize_year(match.group(1))
        month_name = match.group(2).upper()
        add_candidate(
            candidates,
            MONTHS[month_name],
            year,
            match.group(0),
            "YEAR_MONTH_NAME_DAY",
            priority + 15,
        )


# ============================================================
# EXPIRY DATE LABEL DETECTOR
# EXPIRY DATE 04/2027 / EXP DATE 04/27
# ============================================================
def find_expiry_date_label(
    text: str,
    candidates: List[Dict[str, Any]],
    priority: int = 0,
) -> None:
    pattern = re.compile(
        r"(?:EXPIRY\s*DATE|EXP\s*DATE)"
        r"\s*[:\.-]?\s*"
        r"(0?[1-9]|1[0-2])"
        r"\s*[/\-.]\s*"
        r"(19\d{2}|20\d{2}|\d{2})",
        re.IGNORECASE,
    )

    for match in pattern.finditer(text):
        month = int(match.group(1))
        year = normalize_year(match.group(2))
        add_candidate(
            candidates,
            month,
            year,
            match.group(0),
            "EXPIRY_DATE_LABEL",
            priority + 50,
        )


# ============================================================
# REMOVE DUPLICATES
# ============================================================
def remove_duplicates(
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    unique: Dict[Any, Dict[str, Any]] = {}

    for candidate in candidates:
        key = (
            candidate["month"],
            candidate["year"],
        )

        existing = unique.get(key)
        if existing is None or candidate["priority"] > existing["priority"]:
            unique[key] = candidate

    return list(unique.values())


# ============================================================
# CHOOSE EXPIRY DATE
# Latest chronological valid date wins.
# ============================================================
def choose_expiry(
    candidates: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None

    candidates = sorted(
        candidates,
        key=lambda x: (
            x["year"],
            x["month"],
        ),
        reverse=True,
    )

    return candidates[0]


# ============================================================
# DETECTION FUNCTION FOR FASTAPI / IMPORTS
# ============================================================
def detect_expiry_from_image(img_input: Any) -> Dict[str, Any]:
    if isinstance(img_input, str):
        image = cv2.imread(img_input)
    else:
        image = img_input

    if image is None:
        return {
            "expiry_detected": False,
            "expiry": None,
            "month": None,
            "year": None,
            "message": "Could not load image",
        }

    detections = run_ocr(image)

    # Keep the same useful V6 idea: discard very weak OCR before
    # building the combined text, but use a slightly lower threshold
    # for imported FastAPI calls so faint expiry text is not thrown away.
    ocr_text = " ".join(
        text
        for text, score in detections
        if score >= 0.20
    )

    cleaned = clean_text(ocr_text)
    expiry_sections = find_expiry_sections(cleaned)
    expiry_candidates: List[Dict[str, Any]] = []

    # --------------------------------------------------------
    # FIRST PRIORITY: EXPIRY SECTIONS
    # --------------------------------------------------------
    for section in expiry_sections:
        find_expiry_date_label(section, expiry_candidates, priority=120)
        find_month_year(section, expiry_candidates, priority=100)
        find_month_year_with_suffix(section, expiry_candidates, priority=110)
        find_numeric_dates(section, expiry_candidates, priority=100)
        find_compact_expiry_dates(section, expiry_candidates, priority=100)

    # --------------------------------------------------------
    # SEARCH ENTIRE OCR TEXT AS FALLBACK
    # Expiry might not have an EXP keyword.
    # --------------------------------------------------------
    find_month_year(cleaned, expiry_candidates, priority=20)
    find_month_year_with_suffix(cleaned, expiry_candidates, priority=30)
    find_numeric_dates(cleaned, expiry_candidates, priority=20)
    find_year_month_name_day(cleaned, expiry_candidates, priority=40)
    find_compact_expiry_dates(cleaned, expiry_candidates, priority=20)

    unique_candidates = remove_duplicates(expiry_candidates)
    final_candidate = choose_expiry(unique_candidates)

    if final_candidate:
        month = final_candidate["month"]
        year = final_candidate["year"]
        expiry_string = f"{month:02d}/{year}"

        return {
            "expiry_detected": True,
            "expiry": expiry_string,
            "month": month,
            "year": year,
            "source": final_candidate["raw"],
        }

    return {
        "expiry_detected": False,
        "expiry": None,
        "month": None,
        "year": None,
        "message": "expiry date not found. Please try again or type it manually.",
    }


# ============================================================
# CLI RUNNER
# Only runs when this file is executed directly.
# ============================================================
if __name__ == "__main__":
    result = detect_expiry_from_image(INPUT_IMAGE)

    # Preserve the old standalone behavior without saving again when
    # FastAPI imports this module.
    if database is not None:
        try:
            database.save_scan(result)
        except Exception:
            pass

    # Keep stdout machine-readable for expiry_service.py.
    # Any human/debug output should go to stderr.
    print("FINAL_JSON:" + json.dumps(result, ensure_ascii=False))
