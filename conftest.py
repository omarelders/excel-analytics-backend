"""Pytest configuration for the repository root.

Why this file exists
--------------------
The application reads two settings at *import* time, before any fixture can run:

  * database.py builds its engine from DATABASE_URL when it is imported, and raises
    RuntimeError if that variable is missing.
  * main.py computes is_production = (os.getenv("ENV") == "production") at module
    level and uses it to build the CORS allow-list, which is what
    test_security_fixes.py::test_security_headers_and_cors asserts against.

pytest imports conftest.py at startup, ahead of collecting any test module, so a
module-level assignment here is the earliest hook available. It runs before
test_flow.py (which does `from main import app` on line 12) and before
test_security_fixes.py performs its own module-level os.environ assignment. Without
this file the outcome depends on collection order: when test_flow.py is imported
first, `main` is frozen with ENV unset, the localhost origins stay in the CORS
allow-list, and the CORS test fails - a defect in test ordering, not in the
application. Collection order is alphabetical, so test_flow.py always won.

Values are assigned rather than setdefault'd so the suite is deterministic and can
never reach a developer's real database: tests must always run against SQLite.

TRUSTED_PROXY_COUNT is set here for the same reason: main.py refuses to import
under ENV=production when the trusted-proxy topology is undeclared (see
dependencies.configure_proxy_trust), and it is read once, at import time. Without
this line every module that imports `main` would fail to collect. The value is the
production reality - one reverse proxy in front - and tests that need a different
topology set it with monkeypatch.setenv.

These are the same values test_security_fixes.py already sets for itself, so this
changes nothing for the file run on its own - it only makes that guarantee hold when
the whole suite is collected.
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENV"] = "production"
os.environ["TRUSTED_PROXY_COUNT"] = "1"
