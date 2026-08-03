"""Flask + SQLite pytest conftest pattern（每測試獨立臨時 DB + autouse 停外部副作用）。

用法：複製到專案 tests/conftest.py，依專案調整：
- `db.DB_PATH`：專案的 DB path 變數名（db.py 內）
- `db.init_db()`：建表函數
- autouse `_no_network` 內的 monkeypatch 清單：依專案列出所有會打網路/LLM/背景執行緒的函數
  （記住 2026-08-03 教訓：不 mock 網路 → 測試卡 83s；不停 worker → database locked）
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))


@pytest.fixture()
def app():
    """每個測試獨立臨時 DB，隔離真實資料。"""
    tmpdir = tempfile.mkdtemp(prefix='app-test-')
    db_path = os.path.join(tmpdir, 'test.db')

    import db
    db.DB_PATH = db_path  # 覆寫（import app 前）

    import app as app_mod
    db.init_db()
    app_mod.app.config['TESTING'] = True
    yield app_mod.app

    for f in (db_path, db_path + '-wal', db_path + '-shm'):
        try:
            os.unlink(f)
        except OSError:
            pass
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db_conn(app):
    """測試用 db 連線（直接操作）。"""
    import db
    return db.get_db()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """停用所有網路/LLM/背景 worker 呼叫，避免測試卡住或 DB locked。"""
    import routes_bookmarks  # 依專案調整 import
    import routes_notehub
    monkeypatch.setattr(routes_bookmarks, 'fetch_title', lambda url: '')
    monkeypatch.setattr(routes_bookmarks, 'llm_enhance', lambda url, title: ('', ''))
    monkeypatch.setattr(routes_bookmarks, 'extract_favicon', lambda url: '')
    monkeypatch.setattr(routes_notehub, '_ensure_worker', lambda: None)
