# dq_framework — unified Databricks data-quality framework.
#
# The facade (run_row_checks / run_endpoint_checks / run_kpi_asserts) lives in
# dq_framework.facade and is imported lazily so that the pure-Python core
# (dq_framework.core.*) can be imported and unit-tested without pyspark / DQX
# installed. Notebooks do:  from dq_framework import run_row_checks

__all__ = ["run_row_checks", "run_endpoint_checks", "run_kpi_asserts",
           "DQResult", "DataQualityGateError"]


def __getattr__(name):
    # Lazy: importing the facade pulls in pyspark/DQX, which the pure core and
    # its unit tests must not require. Deferred until a facade symbol is used.
    if name in __all__:
        from . import facade
        return getattr(facade, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
