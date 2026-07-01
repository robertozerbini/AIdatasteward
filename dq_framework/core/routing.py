"""Notification routing — pure, no I/O.

Given failed check results and a list of routes, decide which notifications to
send and to whom. A route matches a result when every key in its `match` block
equals the result's field (empty match = catch-all). Each matching route yields
one Notification carrying the results it matched; a result can match several
routes (e.g. a severity route and a target-specific route).
"""
from dataclasses import dataclass, field


@dataclass
class Notification:
    channels: list        # channel names to send on, e.g. ["teams", "jira"]
    recipients: list      # e.g. email addresses for the email channel
    results: list = field(default_factory=list)  # matched failed result dicts


def _matches(result: dict, match: dict) -> bool:
    return all(result.get(k) == v for k, v in match.items())


def build_notifications(results, routes) -> list:
    failures = [r for r in results if r["status"] == "fail"]
    notifications = []
    for route in routes:
        matched = [r for r in failures if _matches(r, route.get("match", {}))]
        if not matched:
            continue
        notifications.append(Notification(
            channels=route.get("channels", []),
            recipients=route.get("email_to", []),
            results=matched,
        ))
    return notifications
