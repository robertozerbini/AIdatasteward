# Notification delivery. Runtime-only (HTTP/SMTP/dbutils secrets). The routing
# and message-rendering logic lives in dq_framework.core.{routing,messages} and
# is unit-tested; this package is thin delivery glue.
from dq_framework.notify.dispatcher import dispatch  # noqa: F401
