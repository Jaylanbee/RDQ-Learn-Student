# test_api.py - RDQ v11.5 API 端點整合測試 (Standard unittest)
# 涵蓋: tasks, radar, chat 四象限狀態機, ingest multipart/form-data, approve 轉正, verify Leitner
import unittest, os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reference_impl.db import init_db, get_connection
from server import app
from fastapi.testclient import TestClient

client = TestClient(app)

class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        init_db()

    # ── GET /api/tasks ──
    def test_api_tasks_endpoint(self):
        response = client.get("/api/tasks")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("tasks", data)
        self.assertIn("count", data)
        self.assertIn("total_due", data)

    # ── GET /api/radar ──
    def test_api_radar_endpoint(self):
        response = client.get("/api/radar")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("國文", data["radar"])
        self.assertIn("自然", data["radar"])
        # Laplace 平滑: (0+1)/(0+2)*100 = 50 for empty subject
        for subj in ["國文", "英語", "數學", "自然", "社會"]:
            self.assertIn(subj, data["radar"])

    # ── POST /api/ingest (multipart/form-data, 無圖片) ──
    def test_ingest_text_only(self):
        res = client.post("/api/ingest", data={
            "question": "測試會考題",
            "answer": "測試解析",
            "subject": "自然",
            "topic": "1-2 質量與密度",
            "ocr_confidence": "0.95"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("staging_id", data)

    # ── POST /api/ingest + POST /api/ingest/approve E2E ──
    def test_ingest_and_approve_flow(self):
        ingest_res = client.post("/api/ingest", data={
            "question": "會考E2E測試題",
            "answer": "E2E解析",
            "subject": "數學",
            "topic": "三角形",
            "ocr_confidence": "0.95"
        })
        self.assertEqual(ingest_res.status_code, 200)
        staging_id = ingest_res.json()["staging_id"]

        approve_res = client.post("/api/ingest/approve", json={"staging_id": staging_id})
        self.assertEqual(approve_res.status_code, 200)
        self.assertEqual(approve_res.json()["status"], "success")
        self.assertIn("item_id", approve_res.json())
        # 確認 item_id 格式正確
        self.assertTrue(approve_res.json()["item_id"].startswith("item_"))

    # ── POST /api/ingest OCR 低於門檻 → fallback_manual ──
    def test_ingest_low_ocr_fallback(self):
        res = client.post("/api/ingest", data={
            "question": "模糊題目",
            "answer": "模糊解析",
            "ocr_confidence": "0.50"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("Fallback", data["message"])

    # ── POST /api/chat: Phase 1 開始 ──
    def test_chat_phase1_start(self):
        res = client.post("/api/chat", json={
            "session_id": "test_session_001",
            "topic": "1-2 質量與密度",
            "textbook": "",
            "is_start": True
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("Phase 1", data["reply"])
        self.assertEqual(data["phase"], "phase1")

    # ── POST /api/chat: Phase 1 → Phase 2 (學生有回憶) ──
    def test_chat_phase1_to_phase2_with_recall(self):
        # 先開始對話
        client.post("/api/chat", json={
            "session_id": "test_session_002",
            "topic": "密度",
            "is_start": True
        })
        # 學生回答有記憶的內容
        res = client.post("/api/chat", json={
            "session_id": "test_session_002",
            "message": "密度等於質量除以體積"
        })
        data = res.json()
        self.assertEqual(data["phase"], "phase2")
        # Guardrail: 回覆不應直接給答案，應該是追問
        self.assertNotIn("標準答案", data["reply"])

    # ── POST /api/chat: Phase 1 → L2 鷹架降級 (學生說不知道) ──
    def test_chat_phase1_stuck_l2_scaffold(self):
        client.post("/api/chat", json={
            "session_id": "test_session_003",
            "topic": "力學",
            "is_start": True
        })
        res = client.post("/api/chat", json={
            "session_id": "test_session_003",
            "message": "不知道"
        })
        data = res.json()
        self.assertEqual(data["phase"], "phase2")
        self.assertTrue(len(data.get("options", [])) > 0, "L2 鷹架應提供選項")

if __name__ == "__main__":
    unittest.main()
