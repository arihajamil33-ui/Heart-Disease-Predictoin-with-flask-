import os
import json
import pickle
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
RISK_THRESHOLD = 0.50
FEATURE_ORDER = [
    "age", "gender", "height", "weight", "ap_hi", "ap_lo",
    "cholesterol", "gluc", "smoke", "alco", "active",
    "bmi", "pulse_pressure",
]
MODEL_FILES = {
    "Logistic Regression": "logistic_regression.pkl",
    "Random Forest": "random_forest.pkl",
    "XGBoost": "xgboost.pkl",
}
LEVEL_LABELS = {1: "Normal", 2: "Above Normal", 3: "Well Above Normal"}
_scaler = None
_models = {}
_best_name = ""
_results = {}


def init():
    global _scaler, _models, _best_name, _results
    _results = _read_json(os.path.join(MODELS_DIR, "results.json"), {})
    feature_names = _read_json(os.path.join(MODELS_DIR, "features.json"),
                               FEATURE_ORDER)
    try:
        with open(os.path.join(MODELS_DIR, "scaler.pkl"), "rb") as f:
            _scaler = pickle.load(f)
    except FileNotFoundError:
        _scaler = None
        print("WARNING: models/scaler.pkl not found - run train_model.py first.")
        return
    for name, filename in MODEL_FILES.items():
        try:
            with open(os.path.join(MODELS_DIR, filename), "rb") as f:
                _models[name] = pickle.load(f)
        except FileNotFoundError:
            print(f"WARNING: models/{filename} not found - run train_model.py first.")
    _best_name = _results.get("best_model", "Random Forest")
    if _models:
        print(f"ML engine ready: scaler loaded, {len(_models)} models "
              f"({', '.join(_models)}); prediction = their average.")


def is_ready():
    return _scaler is not None and len(_models) > 0


def get_feature_names():
    return list(FEATURE_ORDER)


def get_results():
    return _results


def _read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def compute_derived_features(height, weight, ap_hi, ap_lo):
    bmi = weight / ((height / 100) ** 2)
    bmi = round(max(10, min(70, bmi)), 2)
    pulse_pressure = ap_hi - ap_lo
    return bmi, pulse_pressure


def validate_input(form):
    errors = []
    numbers = {}
    ranges = {
        "age":    (18, 120, "Age"),
        "height": (100, 250, "Height"),
        "weight": (20, 200, "Weight"),
        "ap_hi":  (60, 250, "Systolic blood pressure"),
        "ap_lo":  (40, 200, "Diastolic blood pressure"),
    }
    for field, (low, high, label) in ranges.items():
        raw = str(form.get(field, "")).strip()
        if raw == "":
            errors.append(f"{label} is required.")
            continue
        try:
            value = float(raw)
        except ValueError:
            errors.append(f"{label} must be a number.")
            continue
        if not (low <= value <= high):
            errors.append(f"{label} must be between {low} and {high}.")
            continue
        numbers[field] = value
    for field, label in [("age", "Age"), ("height", "Height"),
                         ("ap_hi", "Systolic blood pressure"),
                         ("ap_lo", "Diastolic blood pressure")]:
        if field in numbers and numbers[field] != int(numbers[field]):
            errors.append(f"{label} must be a whole number.")
    choices = {
        "gender": (0, 1),
        "cholesterol": (1, 2, 3),
        "gluc": (1, 2, 3),
        "smoke": (0, 1),
        "alco": (0, 1),
        "active": (0, 1),
    }
    for field, allowed in choices.items():
        try:
            value = int(float(str(form.get(field, "")).strip()))
        except (TypeError, ValueError):
            errors.append("Please choose a value for every question.")
            continue
        if value not in allowed:
            errors.append("Please choose a value for every question.")
    if errors:
        return False, errors
    if numbers["ap_hi"] <= numbers["ap_lo"]:
        errors.append("Systolic blood pressure must be higher than diastolic "
                      "- the two readings may be swapped.")
    bmi = numbers["weight"] / ((numbers["height"] / 100) ** 2)
    if bmi < 12 or bmi > 60:
        errors.append(f"The height and weight give a BMI of {bmi:.1f}, "
                      "which is outside the plausible range - "
                      "please double-check them.")
    return (len(errors) == 0), errors


def prepare_input(form):
    age = int(float(form["age"]))
    gender = int(float(form["gender"]))
    height = int(float(form["height"]))
    weight = float(form["weight"])
    ap_hi = int(float(form["ap_hi"]))
    ap_lo = int(float(form["ap_lo"]))
    cholesterol = int(float(form["cholesterol"]))
    gluc = int(float(form["gluc"]))
    smoke = int(float(form["smoke"]))
    alco = int(float(form["alco"]))
    active = int(float(form["active"]))
    bmi, pulse_pressure = compute_derived_features(height, weight, ap_hi, ap_lo)
    vector = [age, gender, height, weight, ap_hi, ap_lo,
              cholesterol, gluc, smoke, alco, active,
              bmi, pulse_pressure]
    readable = {
        "age": age, "gender": gender, "height": height, "weight": weight,
        "ap_hi": ap_hi, "ap_lo": ap_lo, "cholesterol": cholesterol,
        "gluc": gluc, "smoke": smoke, "alco": alco, "active": active,
        "bmi": bmi, "pulse_pressure": pulse_pressure,
    }
    return vector, readable


def predict(vector):
    if not is_ready():
        raise RuntimeError("No trained model available. Run: python train_model.py")
    import pandas as pd
    frame = pd.DataFrame([vector], columns=get_feature_names())
    scaled = _scaler.transform(frame)
    votes = {}
    for name, model in _models.items():
        votes[name] = float(model.predict_proba(scaled)[0][1])
    probability = sum(votes.values()) / len(votes)
    return {
        "probability": probability,
        "predicted_class": 1 if probability >= RISK_THRESHOLD else 0,
        "model_used": f"Ensemble ({len(votes)} models)",
        "votes": votes,
    }


def get_risk_level(probability):
    if probability < RISK_THRESHOLD:
        return {"label": "LOW RISK", "css": "risk-low", "icon": "check",
                "note": "No significant cardiovascular risk pattern detected."}
    return {"label": "HIGH RISK", "css": "risk-high", "icon": "alert",
            "note": "Several risk indicators are present. "
                    "Please consider consulting a doctor."}


def get_bmi_category(bmi):
    if bmi < 18.5:
        return {"label": "Underweight"}
    if bmi < 25:
        return {"label": "Normal weight"}
    if bmi < 30:
        return {"label": "Overweight"}
    return {"label": "Obese"}


def get_tips(risk_label):
    if risk_label == "HIGH RISK":
        return [
            "Consider seeing a doctor for a full cardiovascular check-up.",
            "Monitor your blood pressure regularly and record the readings.",
            "If you smoke, stopping is the single largest risk reduction available.",
            "Aim for regular gentle exercise and a diet low in salt and fat.",
        ]
    return [
        "Keep up a healthy routine - the indicators look good.",
        "Stay physically active - about 150 minutes of activity per week.",
        "Keep salt and saturated fat low, and avoid smoking.",
        "A routine blood pressure and cholesterol check is still worthwhile.",
    ]


def get_feature_importances():
    if not _models:
        return []
    model = _models.get(_best_name)
    if model is None:
        model = next(iter(_models.values()))
    values = None
    if hasattr(model, "feature_importances_"):
        values = model.feature_importances_
    elif hasattr(model, "coef_"):
        values = [abs(c) for c in model.coef_[0]]
    if values is None or len(values) != len(FEATURE_ORDER):
        return []
    total = sum(values) or 1
    rows = [{"feature": name, "importance": float(value) / total}
            for name, value in zip(FEATURE_ORDER, values)]
    rows.sort(key=lambda r: r["importance"], reverse=True)
    return rows
