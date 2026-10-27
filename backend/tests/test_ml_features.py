import time
import unittest

from backend.app import create_app
from backend.recommender.genre_taxonomy import (
    build_feature_text,
    infer_genre_signals,
    normalize_genre_label,
    unknown_tags,
)


class TestMLFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()
        username = f"ml_features_{time.time_ns()}"
        response = cls.client.post(
            "/api/auth/register",
            json={"username": username, "email": f"{username}@example.com", "password": "test-pass-123"},
        )
        assert response.status_code == 201
        payload = response.get_json()
        cls.user_id = payload["user"]["id"]
        cls.headers = {"Authorization": f"Bearer {payload['token']}"}

    def test_genre_prediction_and_cluster_threshold(self):
        prediction = self.client.post(
            "/api/evaluation/genre-predict",
            json={"title": "A dragon and a hidden kingdom", "tags": "magic, quest"},
        )
        self.assertEqual(prediction.status_code, 200)
        self.assertTrue(prediction.get_json()["predictions"])

        zero = self.client.get(f"/api/recommendations/user/{self.user_id}", headers=self.headers)
        self.assertEqual(zero.status_code, 200)
        self.assertEqual(zero.get_json()["recommendation_strategy"], "popularity")

        self.client.post("/api/ratings", json={"book_id": 1, "rating": 5}, headers=self.headers)
        one = self.client.get(f"/api/recommendations/user/{self.user_id}", headers=self.headers)
        self.assertEqual(one.get_json()["recommendation_strategy"], "content_based")

        for book_id in (2, 3):
            response = self.client.post("/api/ratings", json={"book_id": book_id, "rating": 4}, headers=self.headers)
            self.assertEqual(response.status_code, 200)
        three = self.client.get(f"/api/recommendations/user/{self.user_id}", headers=self.headers)
        self.assertEqual(three.get_json()["recommendation_strategy"], "hybrid")

        cluster = self.client.get(f"/api/users/{self.user_id}/cluster", headers=self.headers)
        self.assertEqual(cluster.status_code, 200)
        self.assertEqual(cluster.get_json()["model"], "K-Means")

    def test_taxonomy_normalizes_aliases_without_target_leakage(self):
        self.assertEqual(normalize_genre_label("Mystery & Thriller"), "Mystery & Thriller")
        self.assertEqual(normalize_genre_label("sci-fi"), "Science Fiction")
        self.assertEqual(infer_genre_signals("space-opera, dragons"), ["Science Fiction", "Fantasy"])
        self.assertEqual(
            infer_genre_signals("dark fantasy, cozy mystery, cyberpunk, coming of age"),
            ["Fantasy", "Mystery & Thriller", "Science Fiction", "Young Adult"],
        )
        self.assertEqual(infer_genre_signals("operatic, dragonborn"), [])
        self.assertEqual(unknown_tags("space-opera, wyrdcore"), ["wyrdcore"])
        feature_text = build_feature_text({
            "title": "A dragon kingdom",
            "authors": "A. Writer",
            "top_tags": "magic, quest",
            "primary_genre": "Fantasy",
        })
        self.assertNotIn("Fantasy", feature_text)
        self.assertIn("genre_signal_fantasy", feature_text)

    def test_prediction_reports_uncertainty_and_multilabel_output(self):
        response = self.client.post(
            "/api/evaluation/genre-predict",
            json={"title": "A dragon kingdom", "tags": "magic, wyrdcore"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn(payload["status"], {"confident", "estimated", "uncertain"})
        self.assertIn("confidence_note", payload)
        self.assertEqual(payload["unknown_tags"], ["wyrdcore"])
        self.assertTrue(payload["multilabel"]["predictions"])


if __name__ == "__main__":
    unittest.main()
