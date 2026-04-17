from .registry import db_route
from .dispatcher import dispatch
from . import handlers  # noqa: F401 — trigger auto-registrazione degli handler
