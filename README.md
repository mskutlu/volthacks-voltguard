VoltGuard — an AI ops copilot for IoT energy fleets
===================================================

Home batteries and solar inverters fail quietly: a voltage sags, a pack runs
hot, a contact sticks open. By the time a human checks a dashboard, the damage
is done. VoltGuard watches every device's telemetry stream, detects anomalies
with rolling z-scores, and turns each one into a plain-English diagnosis with
a concrete remediation action — using Gemini when an API key is present and a
deterministic rule engine as an always-on fallback.

Theme fit: IoT (simulated energy-device fleet) + AI/ML (anomaly detection +
LLM incident diagnosis). Zero-setup demo: one command, no account, no key.

Run it
------

    uv run server.py          # http://localhost:8000  (installs deps on first run)

or with Docker:

    docker build -t voltguard . && docker run -p 8000:8000 voltguard

Optional — live Gemini diagnoses:

    export GEMINI_API_KEY=... # from https://aistudio.google.com/apikey

What you'll see: an 8-device simulated fleet (5 home batteries, 3 solar
inverters) streaming voltage/temperature/load once per second. Faults are
injected randomly (~1% of ticks) — within a couple of minutes an incident
appears in the AI feed with root cause + recommended action, and the device
card goes red with the offending metric's z-score.

Architecture
------------

    devices (simulated)  ->  tick loop (1 Hz telemetry)
                             -> AnomalyDetector (rolling z-score, 2-strike rule)
                             -> diagnosis: Gemini 2.0 Flash | rule engine
                             -> in-memory state (no DB by design)
    dashboard (static HTML/JS, no build step)  <-polls-  GET /api/state

Design choices kept deliberately small:
- In-memory state, no database — a demo fleet has one process.
- Rule engine fallback — the demo never breaks on rate limits or missing keys.
- Z-score detector, not a neural net — explainable thresholds beat a black box
  for ops incidents, and it runs in microseconds.

Tests
-----

    uv run test_voltguard.py

Covers: detector two-strike open/recovery, rule-engine output shape and
severity, Gemini fallback without a key, fault injection realism, tick-loop
state integrity, and the HTTP endpoint.

Files
-----

    server.py           app, simulator, detector, diagnosis (single file)
    static/index.html   dashboard (vanilla JS + canvas sparklines)
    test_voltguard.py   self-checks
    SUBMISSION.md       Devpost submission copy + 3-minute demo video script
