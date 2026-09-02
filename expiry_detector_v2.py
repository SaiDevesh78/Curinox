import cv2
import os
import re
import sys
import json
import database
from rapidocr_onnxruntime import RapidOCR


# ============================================================
# SETTINGS & INITIALIZATION
# ============================================================

OUTPUT_DIR = "uploads/expiry_results"

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)

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
    "DECEMBER": 12
}


# ============================================================
# OCR
# ============================================================

def run_ocr(img):

    try:

        result = ocr(img)

        texts = getattr(
            result,
            "txts",
            None
        )

        scores = getattr(
            result,
            "scores",
            None
        )

        if texts is None:

            return []

        output = []

        for i, text in enumerate(texts):

            score = (
                float(scores[i])
                if scores is not None
                else 0.0
            )

            output.append(
                (
                    str(text),
                    score
                )
            )

        return output

    except Exception as e:

        print(
            "OCR ERROR:",
            e
        )

        return []


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    text = text.upper()

    text = text.replace(
        "–",
        "-"
    )

    text = text.replace(
        "—",
        "-"
    )

    text = text.replace(
        "−",
        "-"
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# EXPIRY KEYWORDS
# ============================================================

EXPIRY_KEYWORD_PATTERN = re.compile(
    r"""
    (
        EXPIRY
        |
        EXPIRATION
        |
        EXP
        |
        E\.X\.P
        |
        E\.X\.P\.
    )
    """,
    re.IGNORECASE | re.VERBOSE
)


def has_expiry_keyword(text):

    return bool(
        EXPIRY_KEYWORD_PATTERN.search(
            text
        )
    )


def find_expiry_sections(text):

    sections = []

    for match in EXPIRY_KEYWORD_PATTERN.finditer(
        text
    ):

        start = match.start()

        section = text[
            start:start + 100
        ]

        sections.append(
            section
        )

    return sections


# ============================================================
# YEAR NORMALIZATION
# ============================================================

def normalize_year(value):

    value = int(value)

    if 1900 <= value <= 2100:

        return value

    if 0 <= value <= 99:

        return 2000 + value

    return None


# ============================================================
# ADD CANDIDATE
# ============================================================

def add_candidate(
    candidates,
    month,
    year,
    raw,
    source,
    priority=0
):

    if month is None:

        return

    if year is None:

        return

    if not 1 <= month <= 12:

        return

    if not 1900 <= year <= 2100:

        return

    candidates.append(
        {
            "month": int(month),
            "year": int(year),
            "raw": raw,
            "source": source,
            "priority": priority
        }
    )


# ============================================================
# MONTH + YEAR DETECTOR
# ============================================================

def find_month_year(
    text,
    candidates,
    priority=0
):

    month_pattern = (
        r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|"
        r"JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|"
        r"NOVEMBER|DECEMBER|"
        r"JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|"
        r"SEP|SEPT|OCT|NOV|DEC)"
    )

    pattern_4 = (
        month_pattern
        + r"\s*[\.\-/]?\s*"
        + r"(19\d{2}|20\d{2})"
    )

    for match in re.finditer(
        pattern_4,
        text,
        re.IGNORECASE
    ):

        month_text = (
            match.group(1)
            .upper()
        )

        year = int(
            match.group(2)
        )

        month = MONTHS.get(
            month_text
        )

        add_candidate(
            candidates,
            month,
            year,
            match.group(0),
            "MONTH_YEAR_4",
            priority
        )

    pattern_2 = (
        month_pattern
        + r"\s*[\.\-/]?\s*"
        + r"(\d{2})(?!\d)"
    )

    for match in re.finditer(
        pattern_2,
        text,
        re.IGNORECASE
    ):

        month_text = (
            match.group(1)
            .upper()
        )

        year_short = int(
            match.group(2)
        )

        month = MONTHS.get(
            month_text
        )

        year = normalize_year(
            year_short
        )

        add_candidate(
            candidates,
            month,
            year,
            match.group(0),
            "MONTH_YEAR_2",
            priority
        )


# ============================================================
# SPECIAL MONTH + YEAR SUFFIX
# ============================================================

def find_month_year_with_suffix(
    text,
    candidates,
    priority=0
):

    month_pattern = (
        r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|"
        r"AUG|SEP|SEPT|OCT|NOV|DEC)"
    )

    pattern = (
        month_pattern
        + r"\s*[\.\-/]?\s*"
        + r"(\d{2})"
        + r"\s*[A-Z]?"
    )

    for match in re.finditer(
        pattern,
        text,
        re.IGNORECASE
    ):

        month_text = (
            match.group(1)
            .upper()
        )

        year_short = int(
            match.group(2)
        )

        month = MONTHS.get(
            month_text
        )

        year = normalize_year(
            year_short
        )

        add_candidate(
            candidates,
            month,
            year,
            match.group(0),
            "MONTH_YEAR_SUFFIX",
            priority + 10
        )


# ============================================================
# NUMERIC DATE DETECTOR
# ============================================================

def find_numeric_dates(
    text,
    candidates,
    priority=0
):

    pattern_year_first = (
        r"(?<!\d)"
        r"(19\d{2}|20\d{2})"
        r"\s*[/\-.]\s*"
        r"(0?[1-9]|1[0-2])"
        r"\s*[/\-.]\s*"
        r"(0?[1-9]|[12]\d|3[01])"
        r"(?!\d)"
    )

    for match in re.finditer(
        pattern_year_first,
        text
    ):

        year = int(
            match.group(1)
        )

        month = int(
            match.group(2)
        )

        add_candidate(
            candidates,
            month,
            year,
            match.group(0),
            "YEAR_MONTH_DAY",
            priority + 20
        )

    pattern_mm_yyyy = (
        r"(?<!\d)"
        r"(0?[1-9]|1[0-2])"
        r"\s*[/\-.]\s*"
        r"(19\d{2}|20\d{2})"
        r"(?!\d)"
    )

    for match in re.finditer(
        pattern_mm_yyyy,
        text
    ):

        month = int(
            match.group(1)
        )

        year = int(
            match.group(2)
        )

        add_candidate(
            candidates,
            month,
            year,
            match.group(0),
            "MM_YYYY",
            priority
        )

    pattern_mm_yy = (
        r"(?<!\d)"
        r"(0?[1-9]|1[0-2])"
        r"\s*[/\-.]\s*"
        r"(\d{2})"
        r"(?!\d)"
    )

    for match in re.finditer(
        pattern_mm_yy,
        text
    ):

        month = int(
            match.group(1)
        )

        year = normalize_year(
            match.group(2)
        )

        add_candidate(
            candidates,
            month,
            year,
            match.group(0),
            "MM_YY",
            priority
        )

    pattern_three = (
        r"(?<!\d)"
        r"(\d{1,2})"
        r"\s*[/\-.]\s*"
        r"(\d{1,2})"
        r"\s*[/\-.]\s*"
        r"(19\d{2}|20\d{2})"
        r"(?!\d)"
    )

    for match in re.finditer(
        pattern_three,
        text
    ):

        first = int(
            match.group(1)
        )

        second = int(
            match.group(2)
        )

        year = int(
            match.group(3)
        )

        if (
            second > 12
            and
            1 <= first <= 12
        ):

            add_candidate(
                candidates,
                first,
                year,
                match.group(0),
                "AMERICAN_MM_DD_YYYY",
                priority + 25
            )

            continue

        if (
            1 <= first <= 31
            and
            1 <= second <= 12
        ):

            add_candidate(
                candidates,
                second,
                year,
                match.group(0),
                "DAY_MONTH_YEAR",
                priority + 5
            )

        elif (
            1 <= first <= 12
            and
            second >= 1
            and
            second <= 99
        ):

            fallback_year = normalize_year(
                second
            )

            add_candidate(
                candidates,
                first,
                fallback_year,
                match.group(0),
                "OCR_THREE_PART_FALLBACK",
                priority
            )


# ============================================================
# COMPACT EXPIRY DATE
# ============================================================

def find_compact_expiry_dates(
    text,
    candidates
):

    pattern = re.compile(
        r"""
        (?:EXPIRYDATE|EXPIRY|EXP)
        \s*
        (
            \d{1,4}
            \s*[/\-.]
            \d{1,4}
            \s*[/\-.]
            \d{2,4}
        )
        """,
        re.IGNORECASE | re.VERBOSE
    )

    for match in pattern.finditer(
        text
    ):

        raw_date = match.group(1)

        find_numeric_dates(
            raw_date,
            candidates,
            priority=100
        )


# ============================================================
# SPECIAL YEAR + MONTH NAME + DAY
# ============================================================

def find_year_month_name_day(
    text,
    candidates,
    priority=0
):

    month_pattern = (
        r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|"
        r"JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|"
        r"NOVEMBER|DECEMBER|"
        r"JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|"
        r"SEP|SEPT|OCT|NOV|DEC)"
    )

    pattern = (
        r"(?<!\d)"
        r"(19\d{2}|20\d{2})"
        + month_pattern
        + r"(0?[1-9]|[12]\d|3[01])?"
        r"(?!\d)"
    )

    for match in re.finditer(
        pattern,
        text,
        re.IGNORECASE
    ):

        year = int(
            match.group(1)
        )

        month_text = (
            match.group(2)
            .upper()
        )

        month = MONTHS.get(
            month_text
        )

        add_candidate(
            candidates,
            month,
            year,
            match.group(0),
            "YEAR_MONTH_NAME_DAY",
            priority + 15
        )


# ============================================================
# REMOVE DUPLICATES & CHOOSE
# ============================================================

def remove_duplicates(
    candidates
):

    unique = {}

    for candidate in candidates:

        key = (
            candidate["month"],
            candidate["year"]
        )

        if key not in unique:

            unique[key] = candidate

        else:

            if (
                candidate["priority"]
                >
                unique[key]["priority"]
            ):

                unique[key] = candidate

    return list(
        unique.values()
    )


def choose_expiry(
    candidates
):

    if not candidates:

        return None

    candidates = sorted(
        candidates,
        key=lambda x: (
            x["year"],
            x["month"],
            x["priority"]
        ),
        reverse=True
    )

    return candidates[0]


# ============================================================
# WRAPPER FUNCTION FOR FASTAPI / EXPORTS
# ============================================================

def detect_expiry_from_image(img_input):

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
            "message": "Could not load image"
        }

    detections = run_ocr(image)

    ocr_text = " ".join(
        text
        for text, score in detections
        if score >= 0.30
    )

    cleaned = clean_text(ocr_text)

    expiry_sections = find_expiry_sections(cleaned)

    expiry_candidates = []

    for section in expiry_sections:

        find_month_year(
            section,
            expiry_candidates,
            priority=100
        )

        find_month_year_with_suffix(
            section,
            expiry_candidates,
            priority=110
        )

        find_numeric_dates(
            section,
            expiry_candidates,
            priority=100
        )

        find_compact_expiry_dates(
            section,
            expiry_candidates
        )

    find_month_year(
        cleaned,
        expiry_candidates,
        priority=20
    )

    find_month_year_with_suffix(
        cleaned,
        expiry_candidates,
        priority=30
    )

    find_numeric_dates(
        cleaned,
        expiry_candidates,
        priority=20
    )

    find_year_month_name_day(
        cleaned,
        expiry_candidates,
        priority=40
    )

    find_compact_expiry_dates(
        cleaned,
        expiry_candidates
    )

    unique_candidates = remove_duplicates(
        expiry_candidates
    )

    final_candidate = choose_expiry(
        unique_candidates
    )

    if final_candidate:

        month = final_candidate["month"]

        year = final_candidate["year"]

        expiry_string = (
            f"{month:02d}/{year}"
        )

        final_result = {
            "expiry_detected": True,
            "expiry": expiry_string,
            "month": month,
            "year": year,
            "source": final_candidate["raw"]
        }

    else:

        message = (
            "expiry date not found. "
            "Please try again or type it manually."
        )

        final_result = {
            "expiry_detected": False,
            "expiry": None,
            "month": None,
            "year": None,
            "message": message
        }

    return final_result


# ============================================================
# CLI RUNNER (ONLY RUNS WHEN DIRECTLY EXECUTED)
# ============================================================

if __name__ == "__main__":

    INPUT_IMAGE = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "uploads/medi2_upscaled.png"
    )

    image = cv2.imread(INPUT_IMAGE)

    if image is None:

        print("ERROR: Could not load image:")

        print(INPUT_IMAGE)

        raise SystemExit

    h, w = image.shape[:2]

    print("=" * 70)

    print("GENERAL EXPIRY DATE DETECTOR V6")

    print("=" * 70)

    print(f"Image : {INPUT_IMAGE}")

    print(f"Size  : {w} x {h}")

    print()

    final_result = detect_expiry_from_image(image)

    database.save_scan(final_result)

    print()

    print("=" * 70)

    print("FINAL JSON")

    print("=" * 70)

    print(
        "FINAL_JSON:"
        +
        json.dumps(
            final_result
        )
    )

    print("=" * 70)

    print(
        "The detector reads printed information using OCR. "
        "It does not independently verify medicine authenticity."
    )