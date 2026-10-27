"""Small, deterministic ML helpers used by the insights page.

The application already ships the catalogue and ratings needed for these
features, so the models are trained lazily from local data and never require a
remote service.  The helpers deliberately degrade to transparent heuristics
when there is not enough application data yet (for example, a brand-new local
database with only one reader).
"""

from collections import Counter, defaultdict
from functools import lru_cache
import json
import os
import re
import tempfile
from threading import Lock

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.calibration import CalibratedClassifierCV
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline

from ..config import Config
from ..models.database_models import Book, Rating

from .genre_taxonomy import (
    CANONICAL_GENRES,
    GENRE_ALIASES,
    build_feature_text,
    infer_genre_signals,
    multilabel_targets,
    normalize_genre_label,
    normalize_text,
    unknown_tags,
)


CONFIDENT_THRESHOLD = 0.70
LOW_CONFIDENCE_THRESHOLD = 0.45
_unknown_tag_lock = Lock()


def _book_text(row):
    """Build leakage-free training text; primary_genre is target-only."""

    return build_feature_text(row)


def _feature_pipeline(classifier):
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            analyzer="word",
            min_df=1,
            max_features=10000,
            sublinear_tf=True,
        )),
        ("classifier", classifier),
    ])


def _feature_vectorizer():
    return TfidfVectorizer(
        ngram_range=(1, 2),
        analyzer="word",
        min_df=1,
        max_features=16000,
        sublinear_tf=True,
    )


def _calibrated_classifier():
    base = _feature_pipeline(
        LinearSVC(class_weight="balanced", random_state=42)
    )
    return CalibratedClassifierCV(base, method="sigmoid", cv=2, n_jobs=-1)


@lru_cache(maxsize=1)
def _genre_model():
    frame = pd.read_csv(Config.BOOKS_CSV)
    frame["primary_genre"] = frame["primary_genre"].fillna("General Fiction").astype(str).map(normalize_genre_label)
    frame = frame[frame["primary_genre"].str.strip() != ""]
    labels = frame["primary_genre"].tolist()
    texts = [_book_text(row) for row in frame.to_dict("records")]
    classes = sorted(set(labels))
    if len(classes) < 2:
        return None
    model = _calibrated_classifier()
    model.fit(texts, labels)
    return model, len(texts), classes, "calibrated sigmoid probabilities (estimated confidence)"


@lru_cache(maxsize=1)
def _multilabel_model():
    frame = pd.read_csv(Config.BOOKS_CSV)
    frame["primary_genre"] = frame["primary_genre"].fillna("General Fiction").astype(str)
    records = frame.to_dict("records")
    texts = [_book_text(row) for row in records]
    labels = [multilabel_targets(row) for row in records]
    labeler = MultiLabelBinarizer(classes=list(CANONICAL_GENRES))
    encoded = labeler.fit_transform(labels)
    # The API multi-label model keeps one shared word-feature matrix.  The
    # offline benchmark also tests character n-grams, but they are not a
    # substitute for reviewed labels and are unnecessary for this live path.
    vectorizer = _feature_vectorizer()
    features = vectorizer.fit_transform(texts)
    multilabel = OneVsRestClassifier(
        LinearSVC(
            class_weight="balanced",
            random_state=42,
        ),
        n_jobs=-1,
    )
    multilabel.fit(features, encoded)
    return vectorizer, multilabel, labeler, len(texts), "estimated scores from weakly supervised metadata-derived secondary labels"


def _record_unknown_tags(tags):
    """Persist local unknown-tag telemetry for later taxonomy review."""

    values = [str(tag).strip() for tag in tags if str(tag).strip()]
    if not values:
        return
    path = os.path.join(Config.ARTIFACTS_DIR, "unknown_genre_tags.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _unknown_tag_lock:
        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, ValueError):
                data = {}
        for tag in values:
            key = normalize_text(tag)
            entry = data.setdefault(key, {"tag": tag, "count": 0})
            entry["count"] += 1
        fd, temp_path = tempfile.mkstemp(prefix="unknown_genre_tags_", suffix=".json", dir=os.path.dirname(path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
            os.replace(temp_path, path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


def _confidence_status(value):
    if value >= CONFIDENT_THRESHOLD:
        return "confident"
    if value >= LOW_CONFIDENCE_THRESHOLD:
        return "estimated"
    return "uncertain"


def predict_genres(payload, limit=3):
    """Predict genres from a title/author/tag text payload."""
    if not isinstance(payload, dict):
        raise ValueError("A prediction object is required")
    text = build_feature_text(payload)
    if len(text) < 2:
        raise ValueError("Provide at least a title, author, or tags")
    tags = payload.get("tags", "")
    unknown = unknown_tags(tags)
    _record_unknown_tags(unknown)
    matched_signals = infer_genre_signals(
            payload.get("title", ""), payload.get("authors", ""), tags
    )
    trained = _genre_model()
    if trained is None:
        return {
            "predictions": [{"genre": "General Fiction", "confidence": 0.0, "confidence_status": "uncertain"}],
            "model": "Calibrated Linear SVM",
            "status": "uncertain",
            "confidence_note": "No trained genre model is available.",
            "unknown_tags": unknown,
            "matched_signals": matched_signals,
        }
    model, sample_count, classes, confidence_note = trained
    probabilities = model.predict_proba([text])[0]
    ranked = np.argsort(probabilities)[::-1][:max(1, min(int(limit), 5))]
    top_confidence = float(probabilities[ranked[0]])
    status = _confidence_status(top_confidence)
    if status == "uncertain":
        confidence_note = f"Estimated confidence is below {LOW_CONFIDENCE_THRESHOLD:.0%}; review the result."
    return {
        "model": "TF-IDF + calibrated Linear SVM",
        "training_samples": sample_count,
        "classes": classes,
        "status": status,
        "confidence_note": confidence_note,
        "unknown_tags": unknown,
        "matched_signals": matched_signals,
        "predictions": [
            {
                "genre": str(model.classes_[index]),
                "confidence": round(float(probabilities[index]), 4),
                "confidence_status": _confidence_status(float(probabilities[index])),
            }
            for index in ranked
        ],
    }


def predict_multilabel_genres(payload, limit=5):
    """Return real multi-label scores from a separate One-vs-Rest model."""

    if not isinstance(payload, dict):
        raise ValueError("A prediction object is required")
    text = build_feature_text(payload)
    if len(text) < 2:
        raise ValueError("Provide at least a title, author, or tags")
    vectorizer, model, labeler, sample_count, training_note = _multilabel_model()
    scores = model.decision_function(vectorizer.transform([text]))[0]
    probabilities = 1.0 / (1.0 + np.exp(-np.clip(scores, -30, 30)))
    ranked = np.argsort(probabilities)[::-1]
    selected = [index for index in ranked if probabilities[index] >= LOW_CONFIDENCE_THRESHOLD][:max(1, min(int(limit), 8))]
    if not selected:
        selected = [int(ranked[0])]
    return {
        "model": "TF-IDF + One-vs-Rest Linear SVM",
        "training_samples": sample_count,
        "training_note": training_note,
        "predictions": [
            {
                "genre": str(labeler.classes_[index]),
                "confidence": round(float(probabilities[index]), 4),
                "confidence_status": _confidence_status(float(probabilities[index])),
            }
            for index in selected
        ],
    }


def _cluster_label(genre_counts):
    top_genre = genre_counts.most_common(1)[0][0] if genre_counts else "Fiction"
    normalized = top_genre.casefold()
    if "fantasy" in normalized or "science fiction" in normalized:
        return "Fantasy & speculative readers"
    if "classic" in normalized or "history" in normalized:
        return "Classics & history readers"
    if "romance" in normalized:
        return "Romance readers"
    if "mystery" in normalized or "thriller" in normalized:
        return "Mystery & thriller readers"
    return "Casual mixed readers"


def _user_genre_profiles(db):
    rows = db.query(Rating.user_id, Book.primary_genre, Rating.rating).join(Book, Book.book_id == Rating.book_id).all()
    profiles = defaultdict(Counter)
    for user_id, genre, rating in rows:
        profiles[int(user_id)][str(genre or "Fiction")] += max(0.1, float(rating))
    return profiles


def cluster_users(db, requested_user_id=None):
    """Cluster application users by weighted genre taste using K-Means."""
    profiles = _user_genre_profiles(db)
    requested_user_id = int(requested_user_id) if requested_user_id is not None else None
    if not profiles:
        return {
            "user_id": requested_user_id,
            "cluster_id": 0,
            "cluster_label": "New readers",
            "top_genres": [],
            "cluster_count": 0,
            "users_in_cluster": 0,
            "model": "K-Means",
            "notice": "Rate three books to calculate a reading taste cluster.",
        }

    genre_names = sorted({genre for counts in profiles.values() for genre in counts})
    user_ids = sorted(profiles)
    matrix = np.array([[profiles[user_id].get(genre, 0.0) for genre in genre_names] for user_id in user_ids], dtype=float)
    if len(user_ids) == 1:
        labels = np.array([0])
        cluster_count = 1
    else:
        cluster_count = min(4, len(user_ids))
        labels = KMeans(n_clusters=cluster_count, random_state=42, n_init=10).fit_predict(matrix)

    clusters = defaultdict(list)
    for user_id, label in zip(user_ids, labels):
        clusters[int(label)].append(user_id)
    target_id = requested_user_id if requested_user_id in profiles else user_ids[0]
    target_index = user_ids.index(target_id)
    target_cluster = int(labels[target_index])
    cluster_members = clusters[target_cluster]
    aggregate = Counter()
    for user_id in cluster_members:
        aggregate.update(profiles[user_id])
    top_genres = [{"genre": genre, "weight": round(float(weight), 2)} for genre, weight in aggregate.most_common(5)]
    return {
        "user_id": requested_user_id,
        "cluster_id": target_cluster,
        "cluster_label": _cluster_label(aggregate),
        "top_genres": top_genres,
        "cluster_count": cluster_count,
        "users_in_cluster": len(cluster_members),
        "model": "K-Means",
        "notice": "Cluster is recalculated from explicit app ratings and used as a soft genre signal.",
    }


def cluster_overview(db):
    profiles = _user_genre_profiles(db)
    if not profiles:
        return {"clusters": [], "model": "K-Means", "user_count": 0}
    details = []
    for user_id in sorted(profiles):
        result = cluster_users(db, user_id)
        details.append(result)
    grouped = {}
    for item in details:
        key = item["cluster_id"]
        grouped.setdefault(key, {"cluster_id": key, "label": item["cluster_label"], "users": 0, "top_genres": item["top_genres"]})
        grouped[key]["users"] += 1
    return {"clusters": list(grouped.values()), "model": "K-Means", "user_count": len(profiles)}


def genre_alias(text):
    normalized = re.sub(r"\s+", " ", str(text or "").strip().casefold())
    return GENRE_ALIASES.get(normalized)
