import importlib
import sys
from pathlib import Path


def test_empty_key_rejected(monkeypatch):
    monkeypatch.setenv("APP_PASS", "foo")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    app = importlib.import_module("app")
    importlib.reload(app)
    assert app.check_key("") is False


def test_settings_reset(monkeypatch):
    monkeypatch.setenv("APP_PASS", "foo")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import streamlit as st
    st.session_state.unlocked = True
    app = importlib.import_module("app")
    importlib.reload(app)

    st.session_state.batch_id_counter = 7
    st.session_state.densities["Water"] = 0.5

    app.reset_session_state()

    st.session_state.unlocked = True
    importlib.reload(app)

    assert st.session_state.batch_id_counter == 1
    assert st.session_state.densities == {"Water": 1.0, "Oil EVO": 0.91}
