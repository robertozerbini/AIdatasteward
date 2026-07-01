from dq_framework.core.gating import decide


def _r(status, severity):
    return {"status": status, "severity": severity}


def test_all_pass_is_not_gated_and_passed():
    verdict = decide([_r("pass", "error"), _r("pass", "warn")])
    assert verdict.passed is True
    assert verdict.gated is False


def test_error_severity_failure_gates():
    verdict = decide([_r("pass", "error"), _r("fail", "error")])
    assert verdict.passed is False
    assert verdict.gated is True


def test_warn_severity_failure_does_not_gate_but_is_not_passed():
    verdict = decide([_r("fail", "warn")])
    assert verdict.passed is False
    assert verdict.gated is False


def test_empty_results_is_passed_and_not_gated():
    verdict = decide([])
    assert verdict.passed is True
    assert verdict.gated is False


def test_mixed_warn_and_error_failures_gate():
    verdict = decide([_r("fail", "warn"), _r("fail", "error")])
    assert verdict.passed is False
    assert verdict.gated is True
