# backup.py - RDQ v11.5 自動備份與 integrity_check 強制還原模組
import os, glob, shutil, datetime, hashlib, sqlite3
from reference_impl.config import BACKUP_RETAIN_COUNT
from reference_impl.db import DB_PATH

def backup_db(enable_checksum: bool = False):
    if not os.path.exists(DB_PATH):
        return None
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = f"{DB_PATH}.{ts}.bak"
    shutil.copy2(DB_PATH, backup_path)

    if enable_checksum:
        checksum = hashlib.sha256(open(backup_path, "rb").read()).hexdigest()
        with open(f"{backup_path}.sha256", "w") as f:
            f.write(checksum)

    backups = sorted(glob.glob(f"{DB_PATH}.*.bak"))
    if len(backups) > BACKUP_RETAIN_COUNT:
        for old in backups[:-BACKUP_RETAIN_COUNT]:
            os.remove(old)
            if os.path.exists(f"{old}.sha256"):
                os.remove(f"{old}.sha256")
    return backup_path

def restore_db(backup_path: str):
    checksum_file = f"{backup_path}.sha256"
    if os.path.exists(checksum_file):
        expected = open(checksum_file).read().strip()
        actual = hashlib.sha256(open(backup_path, "rb").read()).hexdigest()
        if expected != actual:
            raise ValueError("備份檔案 checksum 不符，可能已被竄改或損毀")

    test_conn = sqlite3.connect(backup_path)
    result = test_conn.execute("PRAGMA integrity_check;").fetchone()[0]
    test_conn.close()
    if result != "ok":
        raise ValueError(f"備份檔案結構損毀：{result}")

    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, f"{DB_PATH}.before_restore.bak")
    shutil.copy2(backup_path, DB_PATH)
    return True
