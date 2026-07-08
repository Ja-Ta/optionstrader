"""Report delivery: save to dated files and/or send via SMTP email.

Email configuration comes from environment variables (set them in the file
`.env.daily` next to the repo root — sourced by scripts/daily_cron.sh, never
committed anywhere):

  OPTIONSTRADER_SMTP_HOST      e.g. smtp-mail.outlook.com / smtp.gmail.com
  OPTIONSTRADER_SMTP_PORT     587 (default; STARTTLS)
  OPTIONSTRADER_SMTP_USER     login / sending address
  OPTIONSTRADER_SMTP_PASSWORD app password (most providers require one)
  OPTIONSTRADER_SMTP_FROM     optional; defaults to SMTP_USER
"""

from __future__ import annotations

import os
import smtplib
from datetime import date
from email.message import EmailMessage
from pathlib import Path


def save_report(text: str, save_dir: Path, as_of: date) -> Path:
    """Write reports/daily-YYYY-MM-DD.txt and refresh latest.txt."""
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    dated = save_dir / f"daily-{as_of.isoformat()}.txt"
    dated.write_text(text)
    (save_dir / "latest.txt").write_text(text)
    return dated


def email_report(text: str, to_addr: str, subject: str) -> None:
    """Send the report via SMTP (STARTTLS). Raises RuntimeError with a clear
    message when configuration is missing or sending fails."""
    host = os.environ.get("OPTIONSTRADER_SMTP_HOST")
    user = os.environ.get("OPTIONSTRADER_SMTP_USER")
    password = os.environ.get("OPTIONSTRADER_SMTP_PASSWORD")
    if not (host and user and password):
        missing = [n for n, v in [("OPTIONSTRADER_SMTP_HOST", host),
                                  ("OPTIONSTRADER_SMTP_USER", user),
                                  ("OPTIONSTRADER_SMTP_PASSWORD", password)] if not v]
        raise RuntimeError(
            f"email not configured — missing {', '.join(missing)} "
            "(set them in .env.daily; see src/optionstrader/reporting.py)"
        )
    port = int(os.environ.get("OPTIONSTRADER_SMTP_PORT", "587"))
    from_addr = os.environ.get("OPTIONSTRADER_SMTP_FROM", user)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(text)

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"email send failed via {host}:{port} — {e}") from e
