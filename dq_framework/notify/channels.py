"""Channel adapters: email (SMTP), Microsoft Teams (webhook), Jira (REST).

Each adapter takes the rendered subject/body plus its channel connection config
and a `resolve` function that turns secret references into real values. Runtime.
"""
import smtplib
from email.mime.text import MIMEText


def send_email(subject: str, body: str, recipients: list, conn: dict, resolve) -> None:
    if not recipients:
        return
    from_addr = conn["from_addr"]
    host = conn.get("smtp_host", "localhost")
    port = int(conn.get("smtp_port", 25))

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)

    with smtplib.SMTP(host, port) as server:
        if conn.get("starttls", True):
            server.starttls()
        user = resolve(conn.get("user"))
        password = resolve(conn.get("password"))
        if user and password:
            server.login(user, password)
        server.sendmail(from_addr, recipients, msg.as_string())


def send_teams(subject: str, body: str, conn: dict, resolve) -> None:
    import requests  # provided on the Databricks runtime

    webhook = resolve(conn["webhook"])
    # Simple MessageCard; swap for an Adaptive Card if you want richer formatting.
    card = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "summary": subject,
        "themeColor": "D93F0B",
        "title": subject,
        "text": body.replace("\n", "  \n"),
    }
    resp = requests.post(webhook, json=card, timeout=30)
    resp.raise_for_status()


def send_jira(subject: str, body: str, conn: dict, resolve) -> None:
    import requests

    base = conn["base_url"].rstrip("/")
    user = resolve(conn["user"])
    token = resolve(conn["token"])
    payload = {
        "fields": {
            "project": {"key": conn["project_key"]},
            "summary": subject,
            "description": body,
            "issuetype": {"name": conn.get("issue_type", "Bug")},
        }
    }
    resp = requests.post(
        f"{base}/rest/api/2/issue",
        json=payload,
        auth=(user, token),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()


# channel type -> callable. Email is handled specially (needs recipients).
SENDERS = {
    "teams": send_teams,
    "jira": send_jira,
}
