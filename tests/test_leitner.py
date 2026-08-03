# test_leitner.py - RDQ v11.5 Leitner 排程與配額測試 (Standard unittest)
import unittest, sqlite3, os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reference_impl.server import compute_priority, compute_next_review
from reference_impl.db import get_connection, init_db, now_utc_iso

class TestLeitnerScheduler(unittest.TestCase):
    def test_compute_priority_logic(self):
        item = {"wrong_count": 3, "last_wrong_at": now_utc_iso()}
        p = compute_priority(item)
        self.assertGreaterEqual(p, 60)

    def test_box5_graduation_next_review(self):
        next_rev = compute_next_review(5)
        self.assertIsNone(next_rev)

if __name__ == "__main__":
    unittest.main()
