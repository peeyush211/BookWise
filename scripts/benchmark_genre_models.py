"""Benchmark genre classifiers without leaking primary_genre into features.

Usage:
    python scripts/benchmark_genre_models.py

The report intentionally distinguishes the single-label benchmark from the
weakly supervised multi-label model used by the API.  The current catalogue
does not contain reviewed multi-label annotations.
"""

from __future__ import annotations

import json
import os
import sys

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import Config
from backend.recommender.genre_taxonomy import build_feature_text, normalize_genre_label


def _vectorizer():
    return FeatureUnion([
        (
            "word",
            TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),
                min_df=1,
                max_features=20000,
                sublinear_tf=True,
            ),
        ),
        (
            "char",
            TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                min_df=1,
                max_features=25000,
                sublinear_tf=True,
            ),
        ),
    ])


def _models():
    models = {
        "Logistic Regression": LogisticRegression(max_iter=700, class_weight="balanced", random_state=42),
        "Complement Naive Bayes": ComplementNB(alpha=0.5),
        "Linear SVM": LinearSVC(class_weight="balanced", random_state=42),
        "Random Forest": RandomForestClassifier(
            n_estimators=160,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        ),
    }
    unavailable = []
    try:
        from xgboost import XGBClassifier

        models["XGBoost"] = XGBClassifier(
            n_estimators=140,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="multi:softmax",
            eval_metric="mlogloss",
            random_state=42,
            n_jobs=2,
        )
    except ImportError:
        unavailable.append("XGBoost (package not installed)")
    return models, unavailable


def run_benchmark():
    frame = pd.read_csv(Config.BOOKS_CSV)
    frame["primary_genre"] = frame["primary_genre"].fillna("General Fiction").map(normalize_genre_label)
    texts = [build_feature_text(row) for row in frame.to_dict("records")]
    labels = frame["primary_genre"].tolist()
    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.25, random_state=42, stratify=labels
    )

    results = {}
    models, unavailable = _models()
    for name, classifier in models.items():
        pipeline = Pipeline([("features", _vectorizer()), ("classifier", classifier)])
        pipeline.fit(x_train, y_train)
        predictions = pipeline.predict(x_test)
        results[name] = {
            "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
            "macro_f1": round(float(f1_score(y_test, predictions, average="macro", zero_division=0)), 4),
            "classification_report": classification_report(
                y_test, predictions, output_dict=True, zero_division=0
            ),
        }

    return {
        "dataset": {
            "samples": len(frame),
            "classes": sorted(set(labels)),
            "test_size": 0.25,
            "random_state": 42,
        },
        "feature_policy": "title + authors + tags; primary_genre is target-only",
        "results": results,
        "not_run": unavailable,
        "notes": [
            "Accuracy and macro-F1 are measured on a stratified held-out split.",
            "Character n-grams are used only by this offline benchmark; the live API uses word-level TF-IDF features.",
            "Horror and Adventure have very few examples and their per-class scores are unstable.",
            "The API multi-label model currently uses weak metadata-derived secondary labels; reviewed multi-label annotations are still needed for a fully supervised benchmark.",
        ],
    }


def main():
    result = run_benchmark()
    os.makedirs(Config.ARTIFACTS_DIR, exist_ok=True)
    json_path = os.path.join(Config.ARTIFACTS_DIR, "genre_model_benchmark.json")
    markdown_path = os.path.join(Config.ARTIFACTS_DIR, "genre_model_benchmark.md")
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    lines = [
        "# Genre Model Benchmark",
        "",
        f"Dataset: {result['dataset']['samples']:,} books; stratified test split: {result['dataset']['test_size']:.0%}; random state: {result['dataset']['random_state']}.",
        "",
        "| Model | Accuracy | Macro-F1 |",
        "|---|---:|---:|",
    ]
    for name, values in result["results"].items():
        lines.append(f"| {name} | {values['accuracy']:.4f} | {values['macro_f1']:.4f} |")
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in result["notes"])
    if result["not_run"]:
        lines.extend(["", "## Not run", ""])
        lines.extend(f"- {item}" for item in result["not_run"])
    with open(markdown_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print(json.dumps({name: values for name, values in result["results"].items()}, indent=2))
    print(f"Saved {json_path}")
    print(f"Saved {markdown_path}")


if __name__ == "__main__":
    main()
