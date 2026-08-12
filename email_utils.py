"""Shared email sending for both sites, used for password resets.

Configure via environment variables to send real email through any SMTP
provider (Gmail, Postmark, SendGrid's SMTP endpoint, etc.):
  SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD, FROM_EMAIL

If those aren't set (e.g. running locally), send_email() does not silently
pretend to succeed — it logs the message (including any reset link) to the
server console instead, so local testing still works without a real inbox.
"""
import logging
import os
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger("localfork.email")

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER or "no-reply@localfork.local")


def email_configured():
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_email(to_email, subject, body):
    """Send a plain-text email. Returns True if actually sent via SMTP,
    False if it fell back to logging (dev mode, no SMTP configured)."""
    if not email_configured():
        logger.warning(
            "SMTP not configured — email NOT sent. Would have sent to %s:\nSubject: %s\n\n%s",
            to_email, subject, body,
        )
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, [to_email], msg.as_string())
    return True
