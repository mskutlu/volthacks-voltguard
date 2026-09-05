# /// script
# requires-python = ">=3.11"
# dependencies = ["fastapi>=0.115", "httpx2"]
# ///
"""Self-checks: run with `uv run test_voltguard.py` (no server needed)."""

import os

# Force rule-engine path (no network, no key) for deterministic tests.
os.environ.pop("GEMINI_API_KEY", None)

import server  # noqa: E402


def test_detector_opens_incident_after_two_breaches():
    d = server.AnomalyDetector()
    for i in range(60):  # noisy-but-nominal baseline (flat lines have std=0)
        d.update("dev", "voltage", 48.0 + (0.2 if i % 2 else -0.2))
    # Spike: first breach arms, second confirms.
    first_open, z1 = d.update("dev", "voltage", 60.0)
    second_open, z2 = d.update("dev", "voltage", 60.0)
    assert z1 > 3 and z2 > 3, "spike must produce |z|>3"
    assert first_open is False and second_open is True, "two consecutive breaches must open an incident"


def test_detector_quiet_after_normal_reads():
    d = server.AnomalyDetector()
    for v in [48.0] * 60 + [60.0, 60.0]:  # spike then back to normal
        d.update("dev", "load", v)
    open_now, z = d.update("dev", "load", 48.0)
    assert open_now is False and abs(z) < server.Z_RELEASE


def test_rule_diagnosis_shape_and_severity():
    d = server.rule_diagnosis("bat-01", "temperature", z=6.0)
    assert d["brain"] == "rule-engine" and d["severity"] == "critical"
    assert "bat-01" in d["diagnosis"] and d["action"]
    d2 = server.rule_diagnosis("sol-02", "load", z=3.2)
    assert d2["severity"] == "warning"


def test_gemini_falls_back_without_key():
    assert server.gemini_diagnosis("bat-01", "load", 9.0, 4.0, [4.0] * 40) is None


def test_fault_injection_changes_baseline():
    dev = server.DEVICES[0]
    for _ in range(500):
        v = server._fault_value(dev, "temperature", 100.0)
        assert v > 45, "thermal faults must be hot"


def test_tick_loop_produces_state():
    server.state["incidents"].clear()
    for _ in range(3000):
        server.tick()
    ids = [d["id"] for d in server.state["devices"].values()]
    assert len(ids) == 8
    assert all(server.state["devices"][i]["latest"]["voltage"] > 0 for i in ids)
    assert isinstance(server.state["incidents"], list)


def test_api_state_endpoint():
    from fastapi.testclient import TestClient
    with TestClient(server.app) as client:  # startup runs a few ticks
        r = client.get("/api/state")
        assert r.status_code == 200
        body = r.json()
        assert set(body["devices"]) == {d["id"] for d in server.DEVICES}
        assert "incidents" in body and "ai_brain" in body


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    raise SystemExit(1 if failures else 0)
