"""Phase-0 skeleton: app boots, static wiring works, core never imports fastapi."""

import subprocess
import sys

import pytest

pytest.importorskip("fastapi")

from webapp_stubs import make_client, seed_portfolio  # noqa: E402


def test_home_renders_empty_state(tmp_path):
    client = make_client(tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "Dashboard" in r.text
    assert "No positions" in r.text


def test_home_lists_positions(tmp_path):
    seed_portfolio(tmp_path / "pf.json")
    client = make_client(tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "HLD" in r.text and "long_term" in r.text


def test_static_vendor_assets_served(tmp_path):
    client = make_client(tmp_path)
    for path in ("/static/vendor/htmx.min.js", "/static/vendor/uplot.iife.min.js",
                 "/static/app.css", "/static/app.js"):
        r = client.get(path)
        assert r.status_code == 200, path


def test_core_import_never_pulls_fastapi():
    """The UI must stay optional: importing the core package (and the CLI)
    must not import fastapi or optionstrader.webapp."""
    code = (
        "import sys; import optionstrader, optionstrader.cli, optionstrader.daily; "
        "bad = [m for m in ('fastapi', 'optionstrader.webapp') if m in sys.modules]; "
        "sys.exit(1 if bad else 0)"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert proc.returncode == 0, proc.stderr.decode()
