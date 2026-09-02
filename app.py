from fastapi import FastAPI, UploadFile, File
import cv2
import numpy as np

# Import the main wrapper function from your updated script
from expiry_detector_v2 import detect_expiry_from_image

app = FastAPI()

@app.post("/scan")
async def scan_image(file: UploadFile = File(...)):
    # Read uploaded file bytes into an OpenCV image array
    file_bytes = await file.read()
    nparr = np.frombuffer(file_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Pass the decoded image array directly into the detection function
    result = detect_expiry_from_image(image)
    
    return result