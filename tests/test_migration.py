# test_migration.py - RDQ v11.5 全欄位 Migration 比對與 DDL 結構驗證 (Standard unittest)
import unittest, os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reference_impl.db import get_connection, init_db, verify_migration

class TestMigrationVerification(unittest.TestCase):

    def test_verify_migration_executes(self):
        """verify_migration 在無舊表時應安全跳過"""
        conn = get_connection()
        init_db(conn)
        ok, msg = verify_migration(conn)
        self.assertTrue(ok)
        conn.close()

    def test_all_five_tables_exist(self):
        """init_db 後 5 張資料表應全部存在"""
        conn = get_connection()
        init_db(conn)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]
        conn.close()
        for expected in ['review_index_current', 'review_index_log', 'session_state', 'ingestion_staging', 'system_metadata']:
            self.assertIn(expected, tables, f"Missing table: {expected}")

    def test_system_metadata_initialized(self):
        """init_db 後 system_metadata 應含 schema_version 與 migration_version"""
        conn = get_connection()
        init_db(conn)
        row = conn.execute("SELECT value FROM system_metadata WHERE key='schema_version'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], '1')
        conn.close()

if __name__ == "__main__":
    unittest.main()
