from dq_framework.core.messages import render


def _r(target="t1", check_name="c1", severity="error", actual=2.0, expected=0.0):
    return {"target": target, "check_name": check_name, "severity": severity,
            "check_type": "rowlevel", "status": "fail",
            "actual": actual, "expected": expected}


def test_subject_reports_count():
    subject, _ = render([_r(), _r(check_name="c2")])
    assert "2" in subject


def test_subject_names_single_target():
    subject, _ = render([_r(target="orgstrc")])
    assert "orgstrc" in subject


def test_body_lists_each_failed_check():
    _, body = render([_r(check_name="org_unique"), _r(check_name="name_not_null")])
    assert "org_unique" in body
    assert "name_not_null" in body


def test_body_includes_actual_and_expected():
    _, body = render([_r(actual=5.0, expected=0.0)])
    assert "5" in body and "0" in body


def test_render_handles_multiple_targets_in_subject():
    subject, _ = render([_r(target="a"), _r(target="b")])
    # multi-target summaries should not crash and should indicate more than one
    assert "2" in subject  # 2 failures
