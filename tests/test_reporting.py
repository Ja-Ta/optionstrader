from datetime import date

import pytest

from optionstrader.reporting import email_report, save_report


def test_save_report_writes_dated_and_latest(tmp_path):
    p = save_report("report body", tmp_path / "reports", date(2026, 7, 8))
    assert p.name == "daily-2026-07-08.txt"
    assert p.read_text() == "report body"
    assert (tmp_path / "reports" / "latest.txt").read_text() == "report body"


def test_save_report_latest_tracks_newest(tmp_path):
    save_report("day one", tmp_path, date(2026, 7, 7))
    save_report("day two", tmp_path, date(2026, 7, 8))
    assert (tmp_path / "latest.txt").read_text() == "day two"
    assert (tmp_path / "daily-2026-07-07.txt").read_text() == "day one"


def test_email_unconfigured_raises_helpful_error(monkeypatch):
    for var in ("OPTIONSTRADER_SMTP_HOST", "OPTIONSTRADER_SMTP_USER", "OPTIONSTRADER_SMTP_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="email not configured"):
        email_report("body", "to@example.com", "subject")


def test_email_sends_via_smtp(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=30):
            sent["host"], sent["port"] = host, port

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            sent["tls"] = True

        def login(self, user, password):
            sent["login"] = (user, password)

        def send_message(self, msg):
            sent["to"] = msg["To"]
            sent["subject"] = msg["Subject"]
            sent["body"] = msg.get_content()

    monkeypatch.setenv("OPTIONSTRADER_SMTP_HOST", "smtp.test")
    monkeypatch.setenv("OPTIONSTRADER_SMTP_USER", "u@test")
    monkeypatch.setenv("OPTIONSTRADER_SMTP_PASSWORD", "pw")
    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)

    email_report("hello", "jtarman@hotmail.com", "daily test")
    assert sent["host"] == "smtp.test" and sent["port"] == 587 and sent["tls"]
    assert sent["login"] == ("u@test", "pw")
    assert sent["to"] == "jtarman@hotmail.com" and "hello" in sent["body"]


def test_email_failure_wrapped(monkeypatch):
    class BoomSMTP:
        def __init__(self, *a, **k):
            raise OSError("connection refused")

    monkeypatch.setenv("OPTIONSTRADER_SMTP_HOST", "smtp.test")
    monkeypatch.setenv("OPTIONSTRADER_SMTP_USER", "u@test")
    monkeypatch.setenv("OPTIONSTRADER_SMTP_PASSWORD", "pw")
    monkeypatch.setattr("smtplib.SMTP", BoomSMTP)
    with pytest.raises(RuntimeError, match="email send failed"):
        email_report("body", "to@example.com", "subject")
