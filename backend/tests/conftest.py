"""Test-suite environment.

The suite is explicitly a mock environment: deterministic stand-ins are permitted
here and only here (BuildProduct.md §5, §33). Any real run must leave TEST_MODE unset.
"""

import os

os.environ.setdefault("TEST_MODE", "true")
os.environ.setdefault("DARWINGUARD_TEST", "1")

# backend/.env may carry a live MONGODB_URI (Atlas) on the event machine. The suite
# must stay hermetic: without this, TEST-mode tests would connect to the real
# deployment and write probe state into it. The live round-trip test opts back in
# with ATLAS_LIVE_TESTS=1 (see tests/test_atlas_persistence.py).
if os.environ.get("ATLAS_LIVE_TESTS") != "1":
    os.environ["MONGODB_URI"] = ""
