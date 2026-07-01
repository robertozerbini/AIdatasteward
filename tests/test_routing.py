from dq_framework.core.routing import build_notifications


def _r(status="fail", severity="error", target="t1", check_name="c1", check_type="rowlevel"):
    return {"status": status, "severity": severity, "target": target,
            "check_name": check_name, "check_type": check_type}


def test_no_failures_produces_no_notifications():
    routes = [{"match": {}, "channels": ["email"], "email_to": ["a@b"]}]
    assert build_notifications([_r(status="pass")], routes) == []


def test_catch_all_route_matches_all_failures():
    routes = [{"match": {}, "channels": ["teams"], "email_to": ["a@b"]}]
    notes = build_notifications([_r(), _r(check_name="c2")], routes)
    assert len(notes) == 1
    assert len(notes[0].results) == 2
    assert notes[0].channels == ["teams"]
    assert notes[0].recipients == ["a@b"]


def test_severity_route_matches_only_that_severity():
    routes = [{"match": {"severity": "error"}, "channels": ["jira"]}]
    notes = build_notifications([_r(severity="error"), _r(severity="warn")], routes)
    assert len(notes) == 1
    assert all(r["severity"] == "error" for r in notes[0].results)


def test_target_specific_route_matches_only_that_target():
    routes = [{"match": {"target": "sp_customer_360"}, "channels": ["teams"]}]
    notes = build_notifications(
        [_r(target="sp_customer_360"), _r(target="other")], routes)
    assert len(notes) == 1
    assert notes[0].results[0]["target"] == "sp_customer_360"


def test_multiple_matching_routes_each_produce_a_notification():
    routes = [
        {"match": {"severity": "error"}, "channels": ["jira"]},
        {"match": {"target": "t1"}, "channels": ["teams"]},
    ]
    notes = build_notifications([_r(severity="error", target="t1")], routes)
    assert len(notes) == 2
    assert {n.channels[0] for n in notes} == {"jira", "teams"}


def test_route_without_matches_is_skipped():
    routes = [{"match": {"target": "nope"}, "channels": ["email"]}]
    assert build_notifications([_r()], routes) == []
