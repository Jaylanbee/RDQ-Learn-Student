# test_migration.py - RDQ v11.5 全欄位 Migration 比對測試 (Standard unittest)
import unittest, os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reference_impl.db import get_connection, init_db, verify_migration

class TestMigrationVerification(unittest.TestCase):
    def test_verify_migration_executes(self):
        conn = get_connection()
        init_db(conn)
        ok, msg = verify_migration(conn)
        self.assertTrue(ok)
        conn.close()

if __name__ == "__main__":
    unittest.main()
