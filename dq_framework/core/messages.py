"""Render a human-readable subject + body from failed results — pure, no I/O.

Channel adapters (email/Teams/Jira) reuse this so the message content is
consistent and unit-testable regardless of delivery mechanism.
"""


def render(results) -> tuple[str, str]:
    n = len(results)
    targets = sorted({r["target"] for r in results})
    scope = targets[0] if len(targets) == 1 else f"{len(targets)} targets"

    subject = f"[DQ] {n} failed check(s) on {scope}"

    lines = [f"{n} data-quality check(s) failed:", ""]
    for r in results:
        detail = ""
        if r.get("actual") is not None or r.get("expected") is not None:
            detail = f" (actual={r.get('actual')}, expected={r.get('expected')})"
        lines.append(
            f"- [{r['severity']}] {r['target']} :: {r['check_name']}"
            f" ({r['check_type']}){detail}"
        )
    body = "\n".join(lines)
    return subject, body
