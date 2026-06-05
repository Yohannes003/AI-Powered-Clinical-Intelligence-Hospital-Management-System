"""
XGBoost model training script for ICU risk prediction.
Generates synthetic training data and trains a heart disease risk model.
"""

import os
import pickle
import numpy as np
import pandas as pd
from typing import Tuple
import warnings

# Try to import xgboost and sklearn
try:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: xgboost/sklearn not available. Install with: pip install xgboost scikit-learn")


# Feature names
FEATURE_NAMES = [
    "age",
    "heart_rate",
    "blood_pressure_systolic",
    "blood_pressure_diastolic",
    "respiratory_rate",
    "spo2",
    "temperature",
    "gcs_score",
]


def generate_synthetic_training_data(n_samples: int = 5000, random_state: int = 42) -> pd.DataFrame:
    """
    Generate realistic synthetic ICU training data.
    Based on clinical parameters and outcomes.
    """
    np.random.seed(random_state)

    data = {
        "age": np.random.normal(65, 18, n_samples).clip(18, 100).astype(int),
        "heart_rate": np.random.normal(80, 20, n_samples).clip(30, 180).astype(int),
        "blood_pressure_systolic": np.random.normal(125, 25, n_samples).clip(60, 220).astype(int),
        "blood_pressure_diastolic": np.random.normal(78, 15, n_samples).clip(40, 130).astype(int),
        "respiratory_rate": np.random.normal(18, 6, n_samples).clip(6, 50).astype(int),
        "spo2": np.random.normal(96, 4, n_samples).clip(70, 100),
        "temperature": np.random.normal(37.0, 0.8, n_samples).clip(34.0, 41.0),
        "gcs_score": np.random.choice(
            [15, 15, 15, 14, 14, 13, 12, 10, 9, 8, 6, 5, 4, 3],
            size=n_samples,
            p=(np.array([0.3, 0.2, 0.15, 0.1, 0.08, 0.05, 0.04, 0.03, 0.02, 0.015, 0.01, 0.005, 0.005, 0.005])
               / np.sum([0.3, 0.2, 0.15, 0.1, 0.08, 0.05, 0.04, 0.03, 0.02, 0.015, 0.01, 0.005, 0.005, 0.005]))
        ),
    }

    df = pd.DataFrame(data)

    # Generate target (adverse outcome) based on clinical rules
    risk_score = np.zeros(n_samples)

    # Age factor
    risk_score += np.where(df["age"] > 75, 0.15, 0)
    risk_score += np.where((df["age"] > 65) & (df["age"] <= 75), 0.08, 0)

    # Heart rate
    risk_score += np.where((df["heart_rate"] < 50) | (df["heart_rate"] > 120), 0.2, 0)
    risk_score += np.where((df["heart_rate"] < 60) | (df["heart_rate"] > 100), 0.1, 0)

    # Blood pressure
    risk_score += np.where(df["blood_pressure_systolic"] < 90, 0.25, 0)
    risk_score += np.where(df["blood_pressure_systolic"] > 180, 0.15, 0)
    risk_score += np.where((df["blood_pressure_systolic"] >= 90) & (df["blood_pressure_systolic"] < 100), 0.1, 0)

    # SpO2
    risk_score += np.where(df["spo2"] < 88, 0.3, 0)
    risk_score += np.where((df["spo2"] >= 88) & (df["spo2"] < 92), 0.15, 0)
    risk_score += np.where((df["spo2"] >= 92) & (df["spo2"] < 95), 0.05, 0)

    # Respiratory rate
    risk_score += np.where((df["respiratory_rate"] < 10) | (df["respiratory_rate"] > 30), 0.2, 0)
    risk_score += np.where((df["respiratory_rate"] >= 10) & (df["respiratory_rate"] < 12), 0.1, 0)
    risk_score += np.where(df["respiratory_rate"] > 24, 0.1, 0)

    # Temperature
    risk_score += np.where((df["temperature"] < 35.0) | (df["temperature"] > 39.0), 0.15, 0)
    risk_score += np.where((df["temperature"] >= 35.0) & (df["temperature"] < 36.0), 0.08, 0)

    # GCS
    risk_score += np.where(df["gcs_score"] < 9, 0.25, 0)
    risk_score += np.where((df["gcs_score"] >= 9) & (df["gcs_score"] < 13), 0.12, 0)
    risk_score += np.where((df["gcs_score"] >= 13) & (df["gcs_score"] < 15), 0.05, 0)

    # Add some noise and interaction effects
    risk_score += np.random.normal(0, 0.05, n_samples)

    # Clip and create binary target
    risk_score = risk_score.clip(0, 1)
    df["risk_score"] = risk_score
    df["adverse_outcome"] = (risk_score > 0.5).astype(int)

    return df


def train_model(data: pd.DataFrame) -> Tuple[xgb.XGBClassifier, StandardScaler, dict]:
    """Train XGBoost model on the training data."""
    X = data[FEATURE_NAMES]
    y = data["adverse_outcome"]

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train XGBoost model
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        use_label_encoder=False,
    )

    model.fit(
        X_train_scaled, y_train,
        eval_set=[(X_test_scaled, y_test)],
        verbose=False
    )

    # Evaluate
    y_pred = model.predict(X_test_scaled)
    y_prob = model.predict_proba(X_test_scaled)[:, 1]

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "roc_auc": roc_auc_score(y_test, y_prob),
        "classification_report": classification_report(y_test, y_pred),
        "feature_importance": dict(zip(FEATURE_NAMES, model.feature_importances_.tolist())),
    }

    return model, scaler, metrics


def save_model(model, scaler, filepath: str):
    """Save model and scaler to disk."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    model_data = {
        "model": model,
        "scaler": scaler,
        "feature_names": FEATURE_NAMES,
    }
    with open(filepath, "wb") as f:
        pickle.dump(model_data, f)
    print(f"Model saved to {filepath}")


def main():
    """Main training pipeline."""
    print("=" * 60)
    print("ICU Risk Prediction Model Training")
    print("=" * 60)

    if not SKLEARN_AVAILABLE:
        print("ERROR: Required libraries not installed.")
        print("Run: pip install xgboost scikit-learn pandas numpy")
        return

    # Suppress noisy sklearn warning about feature names in container logs
    warnings.filterwarnings(
        "ignore",
        message="X does not have valid feature names, but StandardScaler was fitted with feature names",
    )

    # If model already exists, skip training to save memory/time on startup
    model_path = os.path.join(os.path.dirname(__file__), "heart_model.pkl")
    if os.path.exists(model_path):
        print(f"Model file already exists at {model_path}; skipping training.")
        return

    # Generate training data
    print("\n1. Generating synthetic training data...")
    data = generate_synthetic_training_data(n_samples=5000)
    print(f"   Generated {len(data)} samples")
    print(f"   Positive cases: {data['adverse_outcome'].sum()} ({data['adverse_outcome'].mean()*100:.1f}%)")

    # Train model
    print("\n2. Training XGBoost model...")
    model, scaler, metrics = train_model(data)

    # Print metrics
    print("\n3. Model Performance:")
    print(f"   Accuracy: {metrics['accuracy']:.4f}")
    print(f"   ROC-AUC: {metrics['roc_auc']:.4f}")
    print("\n   Classification Report:")
    print(metrics["classification_report"])

    print("\n4. Feature Importance:")
    for feature, importance in sorted(
        metrics["feature_importance"].items(),
        key=lambda x: x[1], reverse=True
    ):
        print(f"   {feature}: {importance:.4f}")

    # Save model
    print("\n5. Saving model...")
    model_path = os.path.join(os.path.dirname(__file__), "heart_model.pkl")
    save_model(model, scaler, model_path)

    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
