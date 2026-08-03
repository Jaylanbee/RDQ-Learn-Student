# test_api.py - RDQ v11.5 API 端點整合測試 (Standard unittest)
import unittest, os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reference_impl.server import app
from reference_impl.db import init_db
from fastapi.testclient import TestClient

client = TestClient(app)

class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_api_tasks_endpoint(self):
        response = client.get("/api/tasks")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("tasks", data)

    def test_api_radar_endpoint(self):
        response = client.get("/api/radar")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("國文", data["radar"])

    def test_ingest_and_approve_flow(self):
        ingest_res = client.post("/api/ingest", json={
            "question": "測試會考題", "answer": "測試解析", "subject": "自然", "topic": "1-2 質量與密度", "ocr_confidence": 0.95
        })
        self.assertEqual(ingest_res.status_code, 200)
        staging_id = ingest_res.json()["staging_id"]

        approve_res = client.post("/api/ingest/approve", json={"staging_id": staging_id})
        self.assertEqual(approve_res.status_code, 200)
        self.assertEqual(approve_res.json()["status"], "success")
        self.assertIn("item_id", approve_res.json())

if __name__ == "__main__":
    unittest.main()
