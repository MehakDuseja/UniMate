"""Email delivery for university update notifications."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from dotenv import load_dotenv

if TYPE_CHECKING:
    from notifications.change_detector import DetectedChange

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=True)

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "unimate@localhost")
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "smtp").lower()  # smtp | console


def _format_change_line(change: "DetectedChange") -> str:
    label = change.change_type.replace("_", " ").title()
    return f"• [{label}] {change.summary}\n  {change.url}"


def build_update_email(
    *,
    university_name: str,
    changes: Sequence["DetectedChange"],
) -> tuple[str, str, str]:
    subject = f"UniMate: {university_name} admission update detected"
    lines = [
        f"Hello,",
        "",
        f"We detected updates on official pages for {university_name}:",
        "",
    ]
    for change in changes:
        lines.append(_format_change_line(change))
        lines.append("")

    lines.extend(
        [
            "These alerts are sent only when meaningful changes are detected "
            "(deadlines, fees, eligibility, scholarships, etc.).",
            "",
            "— UniMate Admission Assistant",
        ]
    )
    body_text = "\n".join(lines)

    html_parts = [
        f"<p>We detected updates on official pages for <strong>{university_name}</strong>:</p>",
        "<ul>",
    ]
    for change in changes:
        label = change.change_type.replace("_", " ").title()
        html_parts.append(
            f"<li><strong>[{label}]</strong> {change.summary}<br>"
            f'<a href="{change.url}">{change.url}</a></li>'
        )
    html_parts.append("</ul><p><em>— UniMate Admission Assistant</em></p>")
    body_html = "\n".join(html_parts)

    return subject, body_text, body_html


def send_email(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> None:
    if EMAIL_BACKEND == "console":
        logger.info(
            "EMAIL (console backend)\nTo: %s\nSubject: %s\n\n%s",
            to_email,
            subject,
            body_text,
        )
        print(f"\n--- UniMate email to {to_email} ---\nSubject: {subject}\n{body_text}\n")
        return

    if not SMTP_HOST:
        raise RuntimeError(
            "SMTP_HOST is not configured. Set SMTP_* env vars or EMAIL_BACKEND=console for local testing."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        if SMTP_PORT != 25:
            server.starttls()
            server.ehlo()
        if SMTP_USER and SMTP_PASSWORD:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [to_email], msg.as_string())

    logger.info("Sent email to %s: %s", to_email, subject)


def send_university_update_email(
    *,
    to_email: str,
    university_name: str,
    changes: Sequence["DetectedChange"],
) -> None:
    if not changes:
        return
    subject, body_text, body_html = build_update_email(
        university_name=university_name,
        changes=changes,
    )
    send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )
