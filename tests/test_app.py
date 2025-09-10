import importlib
import sys
from pathlib import Path


def test_empty_key_rejected(monkeypatch):
    monkeypatch.setenv("APP_PASS", "foo")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    app = importlib.import_module("app")
    importlib.reload(app)
    assert app.check_key("") is False


def test_slugify_and_unique_slug(monkeypatch):
    monkeypatch.setenv("APP_PASS", "foo")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    app = importlib.import_module("app")
    importlib.reload(app)
    assert app.slugify("Crème fraîche!") == "creme_fraiche"
    first = app.unique_slug("Crème fraîche")
    second = app.unique_slug("Creme fraiche")
    assert first == "creme_fraiche"
    assert second == "creme_fraiche_1"
