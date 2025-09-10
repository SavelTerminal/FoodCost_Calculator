import importlib
import sys
from pathlib import Path


def test_empty_key_rejected(monkeypatch):
    monkeypatch.setenv("APP_PASS", "foo")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    app = importlib.import_module("app")
    importlib.reload(app)
    assert app.check_key("") is False
