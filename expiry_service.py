import subprocess
import sys
import re
import json


def detect_expiry(image_path):

    result = subprocess.run(
        [
            sys.executable,
            "expiry_detector_v2.py",
            image_path
        ],
        capture_output=True,
        text=True
    )

    output = result.stdout

    # Find the JSON printed by expiry_detector_v2.py
    match = re.search(
        r"FINAL_JSON:(\{.*\})",
        output
    )

    if match:

        return json.loads(match.group(1))

    return {
        "expiry_detected": False,
        "expiry": None,
        "month": None,
        "year": None
    }
