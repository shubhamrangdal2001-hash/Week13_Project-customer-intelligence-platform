"""
train.py – Conversion Prediction Model Training Script
======================================================
Loads campaign CSVs from data/campaign/, trains an XGBoost classifier,
evaluates it, and saves the artifact to models/conversion_model.pkl.

Usage:
    python services/conversion/train.py

Output:
    models/conversion_model.pkl    – trained model + metadata
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    classification_report,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from xgboost import XGBClassifier

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "campaign"
MODEL_DIR = BASE_DIR / "models"
MODEL_PATH = MODEL_DIR / "conversion_model.pkl"
METRICS_PATH = MODEL_DIR / "train_metrics.json"

# ---------------------------------------------------------------------------
# Feature configuration
# ---------------------------------------------------------------------------
# These defaults work for a generic campaign dataset.
# Adjust column names to match your actual CSV schema.
TARGET_COLUMN = os.getenv("TARGET_COLUMN", "converted")
NUMERIC_FEATURES = os.getenv(
    "NUMERIC_FEATURES",
    "age,income,num_campaigns,num_clicks,num_opens,recency_days,tenure_days",
).split(",")
CATEGORICAL_FEATURES = os.getenv(
    "CATEGORICAL_FEATURES",
    "gender,channel,product_category,region",
).split(",")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_data(data_dir: Path) -> pd.DataFrame:
    """Read all CSVs in *data_dir* and concatenate them into one DataFrame."""
    csv_files = list(data_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in {data_dir}. "
            "Place your campaign data there before running training."
        )
    log.info("Loading %d CSV file(s) from %s", len(csv_files), data_dir)
    frames = [pd.read_csv(f) for f in csv_files]
    df = pd.concat(frames, ignore_index=True)
    log.info("Total rows: %d  columns: %d", len(df), df.shape[1])
    return df


def engineer_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Select, encode, and return features (X) and label (y).

    Missing numeric values are imputed with the column median.
    Unknown categoricals are encoded as -1.
    """
    if TARGET_COLUMN not in df.columns:
        raise ValueError(
            f"Target column '{TARGET_COLUMN}' not found. "
            f"Available columns: {list(df.columns)}"
        )

    # Filter to only existing columns to be resilient to schema differences
    num_cols = [c for c in NUMERIC_FEATURES if c in df.columns]
    cat_cols = [c for c in CATEGORICAL_FEATURES if c in df.columns]

    log.info("Numeric features  : %s", num_cols)
    log.info("Categorical features: %s", cat_cols)

    # Numeric imputation
    X_num = df[num_cols].apply(lambda col: col.fillna(col.median()))

    # Label‑encode categoricals
    X_cat = df[cat_cols].copy()
    encoders: dict[str, LabelEncoder] = {}
    for col in cat_cols:
        le = LabelEncoder()
        X_cat[col] = X_cat[col].astype(str).fillna("__missing__")
        X_cat[col] = le.fit_transform(X_cat[col])
        encoders[col] = le

    X = pd.concat([X_num, X_cat], axis=1)
    y = df[TARGET_COLUMN].astype(int)

    return X, y, num_cols, cat_cols, encoders


# ---------------------------------------------------------------------------
# Main training routine
# ---------------------------------------------------------------------------

def train(test_size: float = 0.2, random_state: int = 42) -> dict[str, Any]:
    """Train an XGBoost classifier and persist the artifact."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    df = load_data(DATA_DIR)
    X, y, num_cols, cat_cols, encoders = engineer_features(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    # XGBoost with sensible defaults; tune via environment variables if needed
    model = XGBClassifier(
        n_estimators=int(os.getenv("XGB_N_ESTIMATORS", "300")),
        max_depth=int(os.getenv("XGB_MAX_DEPTH", "6")),
        learning_rate=float(os.getenv("XGB_LR", "0.05")),
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=random_state,
        n_jobs=-1,
        early_stopping_rounds=30,   # stop if val logloss doesn't improve for 30 rounds
    )

    log.info("Training XGBoost…")
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        verbose=50,
    )

    # Evaluation
    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)
    auc = roc_auc_score(y_test, y_prob)
    f1 = f1_score(y_test, y_pred)

    log.info("ROC-AUC : %.4f", auc)
    log.info("F1 Score: %.4f", f1)
    log.info("\n%s", classification_report(y_test, y_pred))

    # Bundle artifact
    artifact: dict[str, Any] = {
        "model": model,
        "feature_columns": num_cols + cat_cols,
        "numeric_features": num_cols,
        "categorical_features": cat_cols,
        "label_encoders": encoders,
        "model_version": "v1.0",
        "metrics": {"roc_auc": auc, "f1": f1},
    }

    with open(MODEL_PATH, "wb") as fh:
        pickle.dump(artifact, fh)
    log.info("Model saved to %s", MODEL_PATH)

    # Save human‑readable metrics
    metrics = {"roc_auc": round(auc, 4), "f1": round(f1, 4)}
    with open(METRICS_PATH, "w") as fh:
        json.dump(metrics, fh, indent=2)
    log.info("Metrics saved to %s", METRICS_PATH)

    return metrics


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train conversion prediction model")
    parser.add_argument("--test-size", type=float, default=0.2, help="Test split ratio")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    metrics = train(test_size=args.test_size, random_state=args.seed)
    print(json.dumps(metrics, indent=2))
