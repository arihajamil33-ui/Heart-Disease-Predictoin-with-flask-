import os
import json
import pickle
import time
import pandas as pd
from sklearn.model_selection import train_test_split, cross_validate
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, confusion_matrix)
from ml_model import compute_derived_features, FEATURE_ORDER, MODEL_FILES, MODELS_DIR
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "heart.csv")


def load_and_clean():
    df = pd.read_csv(DATA_PATH)
    print(f"STEP 1  Loaded: {len(df):,} rows, {len(df.columns)} columns")
    df = df.drop(columns=["id"], errors="ignore")
    if df["age"].max() > 1000:
        df["age"] = (df["age"] / 365.25).round(0).astype(int)
        print("        Age converted from days to years.")
    for col in ["cholesterol", "gluc"]:
        if df[col].min() == 0:
            df[col] = df[col] + 1
            print(f"        '{col}' shifted to the clinical 1-3 scale.")
    before = len(df)
    df = df.drop_duplicates()
    print(f"STEP 3  Duplicates removed: {before - len(df):,} (remaining: {len(df):,})")
    before = len(df)
    df = df[
        df["age"].between(18, 120)
        & df["height"].between(100, 250)
        & df["weight"].between(20, 300)
        & df["ap_hi"].between(60, 250)
        & df["ap_lo"].between(40, 200)
        & (df["ap_hi"] > df["ap_lo"])
        & df["cholesterol"].isin([1, 2, 3])
        & df["gluc"].isin([1, 2, 3])
    ]
    print(f"STEP 4  Impossible values removed: {before - len(df):,} (remaining: {len(df):,})")
    missing = int(df.isnull().sum().sum())
    if missing:
        df = df.fillna(df.median(numeric_only=True))
    print(f"STEP 5  Missing values imputed: {missing}")
    derived = df.apply(
        lambda r: compute_derived_features(r["height"], r["weight"],
                                           r["ap_hi"], r["ap_lo"]), axis=1)
    df["bmi"] = [d[0] for d in derived]
    df["pulse_pressure"] = [d[1] for d in derived]
    print(f"STEP 6  Engineered features added: bmi, pulse_pressure")
    return df


def evaluate(name, model, X_test_scaled, y_test, train_seconds):
    probabilities = model.predict_proba(X_test_scaled)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    return {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "precision": round(float(precision_score(y_test, predictions)), 4),
        "recall": round(float(recall_score(y_test, predictions)), 4),
        "f1": round(float(f1_score(y_test, predictions)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
        "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
        "train_seconds": round(train_seconds, 2),
    }


def cross_validate_model(model, X_train, y_train):
    pipe = Pipeline([("scaler", StandardScaler()), ("model", model)])
    scores = cross_validate(pipe, X_train, y_train, cv=5,
                            scoring=["accuracy", "roc_auc"], n_jobs=-1)
    return {
        "cv_accuracy": round(float(scores["test_accuracy"].mean()), 4),
        "cv_accuracy_std": round(float(scores["test_accuracy"].std()), 4),
        "cv_auc": round(float(scores["test_roc_auc"].mean()), 4),
        "cv_auc_std": round(float(scores["test_roc_auc"].std()), 4),
    }


def train():
    start = time.time()
    df = load_and_clean()
    y = df["cardio"]
    X = df[FEATURE_ORDER]
    print(f"\nDataset ready: {len(df):,} rows | {len(FEATURE_ORDER)} features "
          f"| class balance: {y.value_counts().to_dict()}")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)
    print(f"STEP 7  Train: {len(X_train):,} | Test: {len(X_test):,}")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    print("STEP 8  StandardScaler fitted on the training split")
    models = {
        "Logistic Regression": LogisticRegression(
            max_iter=2000, class_weight="balanced", random_state=42),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=12, min_samples_split=10,
            class_weight="balanced", random_state=42, n_jobs=-1),
        "XGBoost": XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            eval_metric="logloss", random_state=42),
    }
    results = {}
    for name, model in models.items():
        print(f"\nSTEP 9  Training {name}...")
        t0 = time.time()
        model.fit(X_train_scaled, y_train)
        elapsed = time.time() - t0
        row = evaluate(name, model, X_test_scaled, y_test, elapsed)
        row.update(cross_validate_model(model, X_train, y_train))
        results[name] = row
        print(f"        accuracy={row['accuracy']:.4f}  "
              f"precision={row['precision']:.4f}  recall={row['recall']:.4f}  "
              f"f1={row['f1']:.4f}  auc={row['roc_auc']:.4f}  "
              f"cv_auc={row['cv_auc']:.4f}(±{row['cv_auc_std']:.4f})")
    best_model = max(results, key=lambda n: results[n]["roc_auc"])
    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(os.path.join(MODELS_DIR, "scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)
    with open(os.path.join(MODELS_DIR, "features.json"), "w") as f:
        json.dump(FEATURE_ORDER, f)
    for name, model in models.items():
        with open(os.path.join(MODELS_DIR, MODEL_FILES[name]), "wb") as f:
            pickle.dump(model, f)
    summary = {
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": os.path.basename(DATA_PATH),
        "rows_used": len(df),
        "features": FEATURE_ORDER,
        "threshold": 0.5,
        "best_model": best_model,
        "models": results,
    }
    with open(os.path.join(MODELS_DIR, "results.json"), "w") as f:
        json.dump(summary, f, indent=4)
    duration = round(time.time() - start, 1)
    print("\n" + "=" * 72)
    print(f" {'Model':<22}{'Accuracy':>10}{'Precision':>11}{'Recall':>9}"
          f"{'F1':>8}{'ROC AUC':>9}")
    print("-" * 72)
    for name, row in results.items():
        marker = "  <-- selected" if name == best_model else ""
        print(f" {name:<22}{row['accuracy']:>10.4f}{row['precision']:>11.4f}"
              f"{row['recall']:>9.4f}{row['f1']:>8.4f}{row['roc_auc']:>9.4f}{marker}")
    print("=" * 72)
    print(f" Selected model : {best_model} (highest ROC AUC)")
    print(f" Saved to       : models/  (scaler, 3 models, features.json, results.json)")
    print(f" Total time     : {duration}s")
    print("=" * 72 + "\n")
    return summary
if __name__ == "__main__":
    train()
