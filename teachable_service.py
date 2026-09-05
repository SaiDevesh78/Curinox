import os
import cv2
import h5py
import shutil
import numpy as np

# Use the Keras 2 compatibility package with TensorFlow 2.21.
# Teachable Machine's .h5 exports are legacy Keras models.
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

try:
    import tf_keras as keras
except Exception:
    keras = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(BASE_DIR, "model", "keras_model.h5")
LABELS_PATH = os.path.join(BASE_DIR, "model", "labels.txt")
PATCHED_MODEL_PATH = os.path.join(BASE_DIR, "model", "keras_model_compatible.h5")

_model = None
_class_names = []


def _patch_legacy_h5_model() -> str:
    """
    Make a compatibility copy of the original Teachable Machine H5.

    The exported model stores groups=1 in DepthwiseConv2D layer configs.
    That field is redundant for this model and can prevent loading under
    newer runtimes. We remove only that config entry from the COPY and
    leave the original keras_model.h5 untouched.
    """
    if os.path.exists(PATCHED_MODEL_PATH):
        return PATCHED_MODEL_PATH

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(MODEL_PATH)

    shutil.copy2(MODEL_PATH, PATCHED_MODEL_PATH)

    with h5py.File(PATCHED_MODEL_PATH, "r+") as h5_file:
        raw_config = h5_file.attrs.get("model_config")

        if raw_config is None:
            return PATCHED_MODEL_PATH

        if isinstance(raw_config, bytes):
            config_text = raw_config.decode("utf-8")
        else:
            config_text = str(raw_config)

        # Only remove the exact redundant DepthwiseConv2D config field.
        config_text = config_text.replace('"groups": 1,', "")
        config_text = config_text.replace(',"groups": 1', "")

        h5_file.attrs.modify("model_config", config_text)

    return PATCHED_MODEL_PATH


def load_teachable_model():
    global _model, _class_names

    if _model is not None and _class_names:
        return

    if keras is None:
        print(
            "MODEL LOAD ERROR: tf-keras is not installed. "
            "Install it with: python -m pip install tf-keras==2.21.0"
        )
        _model = None
        _class_names = []
        return

    if not os.path.exists(MODEL_PATH):
        print(f"MODEL LOAD ERROR: Missing model file: {MODEL_PATH}")
        _model = None
        _class_names = []
        return

    if not os.path.exists(LABELS_PATH):
        print(f"MODEL LOAD ERROR: Missing labels file: {LABELS_PATH}")
        _model = None
        _class_names = []
        return

    try:
        compatible_model_path = _patch_legacy_h5_model()

        _model = keras.models.load_model(
            compatible_model_path,
            compile=False,
        )

        loaded_labels = []
        with open(LABELS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                clean = line.strip()
                if not clean:
                    continue

                parts = clean.split(" ", 1)
                label = (
                    parts[1].strip()
                    if len(parts) > 1 and parts[0].isdigit()
                    else clean
                )
                loaded_labels.append(label)

        _class_names = loaded_labels

        print("\n=== CURIONIX LEGACY MODEL LOADED ===")
        print("Original model:", MODEL_PATH)
        print("Compatible copy:", compatible_model_path)
        print("Labels:", _class_names)

        try:
            print("Model input shape:", _model.input_shape)
            print("Model output shape:", _model.output_shape)
        except Exception:
            pass

    except Exception as exc:
        print("MODEL LOAD ERROR:", repr(exc))
        _model = None
        _class_names = []


def _fit_image(image):
    """
    Preserve aspect ratio and center-crop to 224x224,
    matching Teachable Machine's ImageOps.fit-style preprocessing.
    """
    height, width = image.shape[:2]

    if height <= 0 or width <= 0:
        return None

    target_size = 224
    scale = max(target_size / width, target_size / height)

    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))

    resized = cv2.resize(
        image,
        (new_width, new_height),
        interpolation=cv2.INTER_LANCZOS4,
    )

    left = max(0, (new_width - target_size) // 2)
    top = max(0, (new_height - target_size) // 2)

    cropped = resized[
        top:top + target_size,
        left:left + target_size,
    ]

    if cropped.shape[0] != target_size or cropped.shape[1] != target_size:
        cropped = cv2.resize(
            cropped,
            (target_size, target_size),
            interpolation=cv2.INTER_LANCZOS4,
        )

    return cropped


def predict_medicine(image_path: str) -> dict:
    load_teachable_model()

    if _model is None or not _class_names:
        return {
            "medicine_name": None,
            "confidence": 0.0,
            "probabilities": {},
        }

    image = cv2.imread(image_path)

    if image is None:
        print("IMAGE ERROR: Could not read:", image_path)
        return {
            "medicine_name": None,
            "confidence": 0.0,
            "probabilities": {},
        }

    try:
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image_fitted = _fit_image(image_rgb)

        if image_fitted is None:
            print("IMAGE ERROR: Could not prepare image.")
            return {
                "medicine_name": None,
                "confidence": 0.0,
                "probabilities": {},
            }

        image_array = np.asarray(image_fitted, dtype=np.float32)
        normalized_image_array = (image_array / 127.5) - 1.0
        input_data = np.expand_dims(normalized_image_array, axis=0)

        prediction = _model.predict(input_data, verbose=0)
        probabilities = np.asarray(
            prediction[0],
            dtype=np.float32,
        ).flatten()

        if probabilities.size == 0:
            print("PREDICTION ERROR: Model returned no probabilities.")
            return {
                "medicine_name": None,
                "confidence": 0.0,
                "probabilities": {},
            }

        if len(_class_names) != len(probabilities):
            print(
                "PREDICTION ERROR: Label count does not match model output.",
                "labels=", len(_class_names),
                "outputs=", len(probabilities),
            )
            return {
                "medicine_name": None,
                "confidence": 0.0,
                "probabilities": {},
            }

        probability_map = {
            _class_names[index]: round(float(probabilities[index]), 6)
            for index in range(len(probabilities))
        }

        top_index = int(np.argmax(probabilities))
        confidence = float(probabilities[top_index])
        medicine_name = _class_names[top_index]

        print("\n--- CURIONIX MODEL PREDICTION ---")
        print("Image:", image_path)

        for label, probability in probability_map.items():
            print(
                f"  {label}: {probability:.6f} "
                f"({probability * 100:.2f}%)"
            )

        print(
            f"TOP: {medicine_name} -> "
            f"{confidence:.6f} ({confidence * 100:.2f}%)"
        )

        return {
            "medicine_name": medicine_name,
            "confidence": round(confidence, 4),
            "probabilities": probability_map,
        }

    except Exception as exc:
        print("MODEL PREDICTION ERROR:", repr(exc))
        return {
            "medicine_name": None,
            "confidence": 0.0,
            "probabilities": {},
        }
