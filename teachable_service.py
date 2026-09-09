import os
import cv2
import h5py
import shutil
import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

try:
    import tf_keras as keras
except Exception:
    try:
        import tensorflow.keras as keras
    except Exception:
        keras = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model", "keras_model.h5")
LABELS_PATH = os.path.join(BASE_DIR, "model", "labels.txt")
PATCHED_MODEL_PATH = os.path.join(BASE_DIR, "model", "keras_model_compatible.h5")

_model = None
_class_names = []


def _patch_legacy_h5_model() -> str:
    """Modifies the legacy H5 file to strip modern Keras compatibility blockers."""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")

    # Regenerate the patched copy whenever the source model is newer, so a
    # retrained/re-exported model.h5 doesn't silently keep using a stale cache.
    if (
        os.path.exists(PATCHED_MODEL_PATH)
        and os.path.getmtime(PATCHED_MODEL_PATH) >= os.path.getmtime(MODEL_PATH)
    ):
        return PATCHED_MODEL_PATH

    shutil.copy2(MODEL_PATH, PATCHED_MODEL_PATH)

    with h5py.File(PATCHED_MODEL_PATH, "r+") as h5_file:
        raw_config = h5_file.attrs.get("model_config")
        if raw_config is None:
            return PATCHED_MODEL_PATH

        if isinstance(raw_config, bytes):
            config_text = raw_config.decode("utf-8")
            is_bytes = True
        else:
            config_text = str(raw_config)
            is_bytes = False

        # Remove 'groups': 1 breaking DepthwiseConv2D in modern Keras/TF
        config_text = config_text.replace('"groups": 1,', "")
        config_text = config_text.replace(',"groups": 1', "")
        config_text = config_text.replace('"groups": 1', "")

        if is_bytes:
            h5_file.attrs.modify("model_config", config_text.encode("utf-8"))
        else:
            h5_file.attrs.modify("model_config", config_text)

    return PATCHED_MODEL_PATH


def load_teachable_model():
    global _model, _class_names

    if _model is not None and _class_names:
        return

    if not os.path.exists(MODEL_PATH):
        print(f"[ERROR] Missing model file at: {MODEL_PATH}")
        return

    if not os.path.exists(LABELS_PATH):
        print(f"[ERROR] Missing labels file at: {LABELS_PATH}")
        return

    try:
        compatible_model_path = _patch_legacy_h5_model()
        
        # Load model using available keras binding
        _model = keras.models.load_model(compatible_model_path, compile=False)

        # Read labels safely
        loaded_labels = []
        with open(LABELS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                clean = line.strip()
                if not clean:
                    continue
                parts = clean.split(" ", 1)
                label = parts[1].strip() if len(parts) > 1 and parts[0].isdigit() else clean
                loaded_labels.append(label)

        _class_names = loaded_labels
        print(f"[SUCCESS] Model Loaded. Labels ({len(_class_names)}): {_class_names}")

    except Exception as exc:
        print("[CRITICAL ERROR] Failed to load Teachable Machine model:")
        import traceback
        traceback.print_exc()
        _model = None
        _class_names = []


def _center_crop_to_square(image: np.ndarray) -> np.ndarray:
    """Crop the largest centered square, matching Teachable Machine's
    own ImageOps.fit() preprocessing. A plain resize would stretch
    non-square photos and distort the medicine box the model was
    trained to recognize."""
    height, width = image.shape[:2]
    if height == width:
        return image

    side = min(height, width)
    top = (height - side) // 2
    left = (width - side) // 2
    return image[top: top + side, left: left + side]


def predict_medicine(image_path: str) -> dict:
    load_teachable_model()

    if _model is None or not _class_names:
        print("[ERROR] Model is not loaded properly.")
        return {"medicine_name": None, "confidence": 0.0, "probabilities": {}}

    if not os.path.exists(image_path):
        print(f"[ERROR] Image path does not exist: {image_path}")
        return {"medicine_name": None, "confidence": 0.0, "probabilities": {}}

    image = cv2.imread(image_path)
    if image is None:
        print(f"[ERROR] OpenCV failed to read image at: {image_path}")
        return {"medicine_name": None, "confidence": 0.0, "probabilities": {}}

    try:
        # 1. Convert BGR (OpenCV default) to RGB (Teachable Machine standard)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 2. Center-crop to square, then resize to 224x224 (matches
        # Teachable Machine's ImageOps.fit inference preprocessing)
        image_square = _center_crop_to_square(image_rgb)
        image_resized = cv2.resize(image_square, (224, 224), interpolation=cv2.INTER_AREA)

        # 3. Normalize image array (-1.0 to 1.0)
        image_array = np.asarray(image_resized, dtype=np.float32)
        normalized_image = (image_array / 127.5) - 1.0
        input_data = np.expand_dims(normalized_image, axis=0)

        # 4. Predict
        prediction = _model.predict(input_data, verbose=0)
        probabilities = np.asarray(prediction[0], dtype=np.float32).flatten()

        # 5. Align labels and probability vector dynamically
        num_outputs = len(probabilities)
        active_labels = _class_names[:num_outputs]

        # Fill with fallback labels if class_names is shorter than output size
        while len(active_labels) < num_outputs:
            active_labels.append(f"Class_{len(active_labels)}")

        probability_map = {
            active_labels[i]: round(float(probabilities[i]), 4)
            for i in range(num_outputs)
        }

        top_index = int(np.argmax(probabilities))
        confidence = float(probabilities[top_index])
        medicine_name = active_labels[top_index]

        return {
            "medicine_name": medicine_name,
            "confidence": round(confidence, 4),
            "probabilities": probability_map,
        }

    except Exception as exc:
        print("[ERROR] Exception during prediction:")
        import traceback
        traceback.print_exc()
        return {"medicine_name": None, "confidence": 0.0, "probabilities": {}}