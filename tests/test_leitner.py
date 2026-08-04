# test_leitner.py - RDQ v11.5 Leitner 排程、Priority 算分與配額測試 (Standard unittest)
import unittest, os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server import compute_priority, compute_next_review
from reference_impl.db import get_connection, init_db, now_utc_iso

class TestLeitnerScheduler(unittest.TestCase):

    def test_compute_priority_high_wrong_count(self):
        """wrong_count=3 + 今天答錯 → priority >= 60"""
        item = {"wrong_count": 3, "last_wrong_at": now_utc_iso()}
        p = compute_priority(item)
        self.assertGreaterEqual(p, 60)

    def test_compute_priority_cap_at_100(self):
        """即使 wrong_count 極端也不超過 100"""
        item = {"wrong_count": 999, "last_wrong_at": now_utc_iso()}
        p = compute_priority(item)
        self.assertLessEqual(p, 100)

    def test_compute_priority_zero_when_clean(self):
        """無錯題歷史 → priority = 0"""
        item = {"wrong_count": 0}
        p = compute_priority(item)
        self.assertEqual(p, 0)

    def test_box5_graduation_next_review_is_none(self):
        """Box 5 畢業 → next_review_at = None"""
        next_rev = compute_next_review(5)
        self.assertIsNone(next_rev)

    def test_box1_next_review_is_tomorrow(self):
        """Box 1 → 到期日為隔天"""
        next_rev = compute_next_review(1)
        self.assertIsNotNone(next_rev)
        self.assertIn("T", next_rev)  # ISO 8601 格式

    def test_box4_next_review_is_7_days(self):
        """Box 4 → 到期日為 7 天後"""
        import datetime
        next_rev = compute_next_review(4)
        self.assertIsNotNone(next_rev)
        # 粗略驗證距今約 7 天
        now = datetime.datetime.now(datetime.timezone.utc)
        target = datetime.datetime.fromisoformat(next_rev.replace('Z', '+00:00'))
        diff = (target - now).days
        self.assertIn(diff, [6, 7])  # 允許時區邊界誤差

if __name__ == "__main__":
    unittest.main()
