# backend/train/train_mbti.py
from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data" / "datasets" / "processed" / "mbti_16p_processed.csv"
META = BASE / "models" / "mbti_meta.json"
MODEL_PATH = BASE / "models" / "mbti.joblib"

def main():
    if not DATA.exists():
        raise SystemExit(f"Missing processed CSV: {DATA}. Run prepare_mbti_16p.py first.")

    meta = json.loads(META.read_text())
    features = meta["feature_names"]
    label_name = meta["label_name"]

    df = pd.read_csv(DATA)
    X = df[features].astype(float)
    y = df[label_name].astype(str)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    pipe = Pipeline([
        ("scaler", StandardScaler(with_mean=True, with_std=True)),
        ("clf", LogisticRegression(max_iter=2000, n_jobs=None, multi_class="auto"))
    ])

    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)

    print("=== Classification Report ===")
    print(classification_report(y_test, y_pred))

    joblib.dump(pipe, MODEL_PATH)
    print(f"✓ Saved model to {MODEL_PATH}")

if __name__ == "__main__":
    main()
