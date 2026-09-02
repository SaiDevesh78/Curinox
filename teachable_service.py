import numpy as np
import cv2
import os
from tensorflow.keras.models import load_model

MODEL_PATH = os.path.join("model", "keras_model.h5")
LABELS_PATH = os.path.join("model", "labels.txt")

# Global variables for model lazy loading
_model = None
_class_names = []


def load_teachable_model():
    global _model, _class_names
    if _model is None and os.path.exists(MODEL_PATH) and os.path.exists(LABELS_PATH):
        _model = load_model(MODEL_PATH, compile=False)
        with open(LABELS_PATH, "r") as f:
            _class_names = [line.strip().split(" ", 1)[-1] for line in f.readlines()]


def predict_medicine(image_path: str) -> dict:
    load_teachable_model()

    if _model is None or not _class_names:
        return {"medicine_name": "Unknown", "confidence": 0.0}

    image = cv2.imread(image_path)
    if image is None:
        return {"medicine_name": "Unknown", "confidence": 0.0}

    # Convert BGR to RGB (Required for Teachable Machine models)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Resize to 224x224 (Standard Teachable Machine input size)
    image_resized = cv2.resize(image_rgb, (224, 224), interpolation=cv2.INTER_AREA)

    # Normalize image tensor (-1.0 to 1.0)
    image_array = np.asarray(image_resized, dtype=np.float32).reshape(1, 224, 224, 3)
    normalized_image_array = (image_array / 127.5) - 1.0

    # Predict
    prediction = _model.predict(normalized_image_array, verbose=0)
    
    # Get top prediction index from the 1D predictions array
    top_index = int(np.argmax(prediction[0]))

    confidence = round(float(prediction[0][top_index]), 2)
    medicine_name = _class_names[top_index]

    return {
        "medicine_name": medicine_name,
        "confidence": confidence
    }