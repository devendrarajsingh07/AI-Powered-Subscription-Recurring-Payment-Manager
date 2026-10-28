"""A substring match must not certify an unsafe or ambiguous static-host policy."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/smoke_deployed.py"
pytestmark = pytest.mark.skipif(not SCRIPT.exists(), reason="root scripts not mounted")
POLICY = "script-src 'self'; style-src 'self'; style-src-elem 'self'; style-src-attr 'none'"


@pytest.mark.parametrize(
    "policy,valid",
    [
        (POLICY, True),
        (POLICY.replace("style-src 'self'", "style-src 'self' 'unsafe-inline'"), False),
        (POLICY.replace("style-src-attr 'none'", "style-src-attr 'unsafe-inline'"), False),
        (POLICY.replace("style-src-elem 'self'; ", ""), False),
        (POLICY.replace("script-src 'self'", "script-src 'self' 'unsafe-eval'"), False),
        (POLICY + "; style-src 'unsafe-inline'", False),
    ],
)
def test_static_host_style_policy(policy, valid):
    spec = importlib.util.spec_from_file_location("csp_smoke_subject", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.strict_style_policy(policy) is valid
