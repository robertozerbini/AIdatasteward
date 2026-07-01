"""Dispatch notifications to their configured channels. Runtime.

Ties the pure routing/rendering to the channel adapters and resolves secret
references (``{secret: {scope, key}}``) via Databricks secrets by default.
"""
from dq_framework.core.messages import render
from dq_framework.core.routing import build_notifications
from dq_framework.notify import channels as ch


def _default_resolver(scope: str, key: str) -> str:
    # Imported lazily so unit tests / non-Databricks contexts don't need dbutils.
    from pyspark.sql import SparkSession
    from pyspark.dbutils import DBUtils

    return DBUtils(SparkSession.getActiveSession()).secrets.get(scope, key)


def _make_resolve(secret_resolver):
    def resolve(value):
        # Literal value, a secret reference, or None.
        if isinstance(value, dict) and "secret" in value:
            s = value["secret"]
            return secret_resolver(s["scope"], s["key"])
        return value
    return resolve


def dispatch(results, notify_config: dict, *, secret_resolver=None) -> list:
    """Send notifications for failed `results` per `notify_config`.

    notify_config = {"channels": {...}, "routes": [...]}.
    Returns the list of (channel, recipients) actually delivered, for logging.
    Never raises on a single channel failure — collects and re-raises at the end
    so one bad webhook doesn't suppress the others.
    """
    routes = notify_config.get("routes", [])
    channels_cfg = notify_config.get("channels", {})
    resolve = _make_resolve(secret_resolver or _default_resolver)

    notifications = build_notifications(results, routes)
    delivered, errors = [], []

    for note in notifications:
        subject, body = render(note.results)
        for channel_name in note.channels:
            conn = channels_cfg.get(channel_name)
            if conn is None:
                errors.append(f"unknown channel: {channel_name}")
                continue
            try:
                ctype = conn["type"]
                if ctype == "email":
                    ch.send_email(subject, body, note.recipients, conn, resolve)
                elif ctype in ch.SENDERS:
                    ch.SENDERS[ctype](subject, body, conn, resolve)
                else:
                    errors.append(f"unsupported channel type: {ctype}")
                    continue
                delivered.append((channel_name, note.recipients))
            except Exception as e:  # keep other channels working
                errors.append(f"{channel_name}: {e}")

    if errors:
        raise RuntimeError("notification errors: " + "; ".join(errors))
    return delivered
