"""Opt-in live Meterless H-MEM integration gate.

The public Meterless material reviewed by this project does not define a
stable hosted Python/HTTP H-MEM contract, so the default suite skips this test.
Once a verified runtime adapter is supplied, set METERLESS_HMEM_LIVE_TEST=1
and replace the marked adapter call with that implementation's round-trip.
"""

import os

import pytest


@pytest.mark.integration
def test_meterless_hmem_live_round_trip_is_explicitly_opt_in():
    if os.getenv("METERLESS_HMEM_LIVE_TEST") != "1":
        pytest.skip("Set METERLESS_HMEM_LIVE_TEST=1 after configuring a verified Meterless H-MEM adapter")
    pytest.fail(
        "Live Meterless H-MEM runtime contract is not verified in this repository; "
        "wire the official adapter here before claiming a live integration pass."
    )
