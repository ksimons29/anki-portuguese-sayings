import csv
import errno
import json
import sys
from pathlib import Path
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import transform_inbox_to_csv as mod


@pytest.fixture
def tmp_base(monkeypatch, tmp_path):
    monkeypatch.setenv("MOCK_LLM", "1")
    monkeypatch.setenv("ANKI_BASE", str(tmp_path))
    base = tmp_path
    mod.BASE = base
    mod.INBOX_DIR = base / "inbox"
    mod.INBOX_FILE = mod.INBOX_DIR / "quick.jsonl"
    mod.MASTER_CSV = base / "sayings.csv"
    mod.LAST_IMPORT = base / "last_import.csv"
    mod.LOG_DIR = base / "logs"
    return base


def test_get_anki_base_env_override(monkeypatch, tmp_path):
    target = tmp_path / "my-anki"
    monkeypatch.setenv("ANKI_BASE", str(target))
    assert mod.get_anki_base() == target


def test_get_anki_base_mobile_preferred(monkeypatch, tmp_path):
    home = tmp_path
    mobile = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Portuguese" / "Anki"
    mobile.mkdir(parents=True)
    monkeypatch.delenv("ANKI_BASE", raising=False)
    monkeypatch.setattr(mod.Path, "home", lambda: home)
    assert mod.get_anki_base() == mobile


def test_get_anki_base_cloud_fallback(monkeypatch, tmp_path):
    home = tmp_path
    cloud = home / "Library" / "CloudStorage" / "iCloud Drive" / "Portuguese" / "Anki"
    cloud.mkdir(parents=True)
    monkeypatch.delenv("ANKI_BASE", raising=False)
    monkeypatch.setattr(mod.Path, "home", lambda: home)
    assert mod.get_anki_base() == cloud


def test_read_quick_entries_handles_mixed_payloads(tmp_path):
    inbox = tmp_path / "quick.jsonl"
    lines = [
        {"entries": "print, copy"},
        {"entries": ["scan", " fax "]},
        {"word": "laminate"},
        {"text": "draft"},
        "not json",
        {"entries": 123},
        {"entries": ["", "   "]},
    ]
    with inbox.open("w", encoding="utf-8") as fh:
        for item in lines:
            if isinstance(item, str):
                fh.write(item + "\n")
            else:
                fh.write(json.dumps(item) + "\n")

    result = mod.read_quick_entries(inbox)
    assert result == ["print", "copy", "scan", "fax", "laminate", "draft"]


def test_extract_lemma_variants():
    assert mod.extract_lemma("Romantic date") == ("Romantic date", "short-phrase")
    assert mod.extract_lemma("I have to print this page.") == ("print", "to-VERB")
    assert mod.extract_lemma("This is the page.") is None
    lemma, rule = mod.extract_lemma("Keep the refrigerator organized")
    assert lemma == "refrigerator"
    assert rule == "content-longest"


def test_append_rows_and_load_existing(tmp_path):
    csv_path = tmp_path / "sayings.csv"
    rows = [["Hello", "Olá", "Isto é um teste.", "This is a test.", "2024-01-01"]]
    mod.append_rows(csv_path, rows)
    assert csv_path.exists()
    with csv_path.open(encoding="utf-8") as fh:
        reader = list(csv.reader(fh))
    assert reader[0] == ["word_en", "word_pt", "sentence_pt", "sentence_en", "date_added"]
    assert reader[1][0] == "Hello"
    seen = mod.load_existing_words(csv_path)
    assert "hello" in seen


def test_open_with_retry_handles_transient_busy(monkeypatch, tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("payload", encoding="utf-8")
    original_open = mod.Path.open
    attempts = {"count": 0}

    def flaky_open(self, *args, **kwargs):
        if self == target and attempts["count"] < 2:
            attempts["count"] += 1
            err = BlockingIOError(errno.EAGAIN, "busy")
            err.errno = errno.EAGAIN
            raise err
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(mod.Path, "open", flaky_open, raising=False)
    with mod._open_with_retry(target) as fh:
        data = fh.read()
    assert data == "payload"
    assert attempts["count"] == 2


def test_anki_invoke_autostarts_on_connection_refused(monkeypatch):
    class DummyResp:
        def __init__(self, payload: dict):
            self._payload = json.dumps(payload).encode("utf-8")

        def read(self) -> bytes:
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    attempts = {"count": 0}

    def fake_urlopen(req, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise URLError(ConnectionRefusedError(errno.ECONNREFUSED, "refused"))
        return DummyResp({"result": "pong"})

    popen_args = []

    class DummyProc:
        pass

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(mod.subprocess, "Popen", lambda cmd: popen_args.append(cmd) or DummyProc())
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    mod._anki_launch_attempted = False

    result = mod.anki_invoke({"action": "ping"})
    assert result == {"result": "pong"}
    assert attempts["count"] == 2  # retried once
    assert popen_args  # ensured we tried to start Anki


def test_refresh_anki_ui_calls_gui_refresh(monkeypatch):
    payloads = []

    def fake_invoke(payload):
        payloads.append(payload)
        return {}

    monkeypatch.setattr(mod, "anki_invoke", fake_invoke)
    mod.refresh_anki_ui()
    assert payloads == [{"action": "gui.refreshAll", "version": 6}]


def test_main_dry_run_skips_io(tmp_base):
    mod.INBOX_DIR.mkdir(parents=True, exist_ok=True)
    mod.INBOX_FILE.write_text(json.dumps({"word": "Practice patience"}) + "\n", encoding="utf-8")
    exit_code = mod.main(["--dry-run", "--log-level", "SILENT"])
    assert exit_code == 0
    assert not mod.MASTER_CSV.exists()
    assert not mod.LAST_IMPORT.exists()


def test_main_writes_csv_and_calls_anki(monkeypatch, tmp_base):
    calls = {}

    def fake_add_notes(deck, model, rows):
        calls["deck"] = deck
        calls["model"] = model
        calls["rows"] = rows
        return len(rows), [42] * len(rows)

    monkeypatch.setattr(mod, "add_notes_to_anki", fake_add_notes)
    refresh_called = {"count": 0}
    monkeypatch.setattr(mod, "refresh_anki_ui", lambda: refresh_called.__setitem__("count", refresh_called["count"] + 1))
    mod.INBOX_DIR.mkdir(parents=True, exist_ok=True)
    mod.INBOX_FILE.write_text(
        json.dumps({"entries": ["focus, energy"]}) + "\n", encoding="utf-8"
    )
    exit_code = mod.main(["--log-level", "SILENT"])
    assert exit_code == 0
    assert mod.MASTER_CSV.exists()
    assert mod.LAST_IMPORT.exists()
    with mod.MASTER_CSV.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["word_en", "word_pt", "sentence_pt", "sentence_en", "date_added"]
    assert rows[1][0] == "mock"
    assert calls["deck"] == "Portuguese Mastery (pt-PT)"
    assert calls["model"] == "GPT Vocabulary Automater"
    assert len(calls["rows"]) == 2
    assert refresh_called["count"] == 1
