# /// script
# requires-python = ">=3.11"
# dependencies = ["fastapi>=0.115", "uvicorn>=0.30"]
# ///
"""VoltGuard — AI ops copilot for IoT energy fleets.

Simulated fleet of battery/solar sensors -> streaming telemetry -> z-score
anomaly detection -> AI diagnosis (Gemini if GEMINI_API_KEY is set, rule
engine otherwise) -> live dashboard.

Run:  uv run server.py     (then open http://localhost:8000)
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import random
import statistics
import time
import urllib.request
from collections import deque
from contextlib import asynccontextmanager
from typing import AsyncIterator, Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

WINDOW = 120          # telemetry points kept per device
Z_TRIGGER = 3.0       # |z-score| that opens an incident
Z_RELEASE = 2.0       # |z-score| below which an incident recovers
TICK_SECONDS = 1.0    # telemetry cadence
METRICS = ("voltage", "temperature", "load")

# ---------------------------------------------------------------------------
# Simulated fleet
# ---------------------------------------------------------------------------

DEVICES = [
    {"id": f"bat-{i:02d}", "kind": "home-battery", "site": site}
    for i, site in zip(range(1, 6), ("North", "South", "East", "West", "Depot"))
] + [
    {"id": f"sol-{i:02d}", "kind": "solar-inverter", "site": site}
    for i, site in zip(range(1, 4), ("Rooftop-A", "Rooftop-B", "Field"))
]


def _baseline(device: dict[str, str], metric: str, t: float) -> float:
    base = {
        "voltage": 48.0 if device["kind"] == "home-battery" else 240.0,
        "temperature": 32.0,
        "load": 4.0 if device["kind"] == "home-battery" else 6.0,
    }[metric]
    wave = math.sin(t / 30 + hash(device["id"]) % 7) * (0.15 * base / 10)
    return base + wave + random.gauss(0, base * 0.004)


def _fault_value(device: dict[str, str], metric: str, t: float) -> float:
    """Faulted reading; caller decides when to inject (see tick)."""
    if metric == "voltage":
        return _baseline(device, metric, t) * random.uniform(0.82, 0.9)   # voltage sag
    if metric == "temperature":
        return _baseline(device, metric, t) + random.uniform(18, 30)      # thermal event
    return _baseline(device, metric, t) * random.uniform(1.8, 2.6)        # load spike


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """Rolling z-score per (device, metric). Incident = 2 consecutive breaches."""

    def __init__(self) -> None:
        self.series: dict[tuple[str, str], deque[float]] = {}
        self.streaks: dict[tuple[str, str], int] = {}

    def update(self, device_id: str, metric: str, value: float) -> tuple[bool, float]:
        key = (device_id, metric)
        hist = self.series.setdefault(key, deque(maxlen=WINDOW))
        z = 0.0
        if len(hist) >= 30:
            mean = statistics.fmean(hist)
            std = statistics.pstdev(hist)
            if std > 1e-9:
                z = (value - mean) / std
        hist.append(value)
        streak = self.streaks.get(key, 0)
        streak = streak + 1 if abs(z) >= Z_TRIGGER else 0
        self.streaks[key] = streak
        return streak >= 2, z


# ---------------------------------------------------------------------------
# Diagnosis: rule engine (always available) + Gemini (optional)
# ---------------------------------------------------------------------------

RULES = {
    "voltage": (
        "Voltage sag on {id}: reading dropped well below the 30-tick baseline — "
        "classic cell-imbalance or loose DC terminal signature.",
        "Dispatch a tech to torque DC terminals and run a cell-balancing cycle on {id}; "
        "if sag persists below 44V, take the pack offline.",
    ),
    "temperature": (
        "Thermal event on {id}: temperature is far above baseline and climbing — "
        "risk of thermal runaway in the pack or a blocked cooling path.",
        "Throttle {id} charging to 50% now, verify enclosure airflow remotely, and "
        "schedule an on-site inspection within 24h.",
    ),
    "load": (
        "Load spike on {id}: demand roughly doubled vs baseline — likely a stuck "
        "contact driving an uncontrolled draw.",
        "Enable the remote disconnect on {id}'s high-draw circuit and cap output "
        "until the site owner confirms the connected load.",
    ),
}


def rule_diagnosis(device_id: str, metric: str, z: float) -> dict[str, str]:
    diagnosis, action = RULES[metric]
    severity = "critical" if abs(z) >= 5 else "warning"
    return {
        "diagnosis": diagnosis.format(id=device_id),
        "action": action.format(id=device_id),
        "severity": severity,
        "brain": "rule-engine",
    }


def gemini_diagnosis(device_id: str, metric: str, value: float, z: float,
                     recent: list[float]) -> dict[str, str] | None:
    """Ask Gemini for a diagnosis; any failure -> None (caller falls back)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    prompt = (
        "You are an ops engineer for a fleet of home-battery and solar-inverter "
        f"IoT devices. Device {device_id} raised an anomaly on metric '{metric}' "
        f"(value {value:.1f}, z-score {z:.1f}). Recent readings: "
        f"{[round(v, 1) for v in recent[-40:]]}. "
        "Reply with ONLY a JSON object: {\"diagnosis\": one sentence root cause, "
        "\"action\": one imperative remediation step, \"severity\": \"warning\" or \"critical\"}."
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
        data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = json.load(resp)["candidates"][0]["content"]["parts"][0]["text"]
        out = json.loads(text)
        return {
            "diagnosis": str(out["diagnosis"]),
            "action": str(out["action"]),
            "severity": out.get("severity") if out.get("severity") in ("warning", "critical") else "warning",
            "brain": "gemini",
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# In-memory state + background tick loop
# ---------------------------------------------------------------------------

state: dict[str, Any] = {
    "started_at": time.time(),
    "devices": {d["id"]: {**d, "latest": {}, "status": "healthy"} for d in DEVICES},
    "incidents": [],   # newest first, capped
    "ai_brain": "rule-engine",
}
detector = AnomalyDetector()
next_fault: dict[str, tuple[str, int]] = {}   # device -> (metric, ticks_remaining)


def tick() -> None:
    t = time.time()
    for device in DEVICES:
        did = device["id"]
        # Pick at most one metric per device to fault this tick.
        fault_metric = None
        if did not in next_fault and random.random() < 0.01:
            next_fault[did] = (random.choice(METRICS), random.randint(8, 15))
        if did in next_fault:
            m, remaining = next_fault[did]
            if remaining <= 0:
                del next_fault[did]
            else:
                next_fault[did] = (m, remaining - 1)
                fault_metric = m
        for m in METRICS:
            value = _fault_value(device, m, t) if m == fault_metric else _baseline(device, m, t)
            incident_open, z = detector.update(did, m, value)
            state["devices"][did]["latest"][m] = round(value, 2)
            state["devices"][did]["latest"][f"{m}_z"] = round(z, 2)
            active = next((i for i in state["incidents"]
                           if i["device"] == did and i["metric"] == m and i["status"] == "open"), None)
            if incident_open and active is None:
                diag = (gemini_diagnosis(did, m, value, z, list(detector.series[(did, m)]))
                        or rule_diagnosis(did, m, z))
                state["ai_brain"] = diag["brain"]
                state["incidents"].insert(0, {
                    "id": f"inc-{len(state['incidents']) + 1}",
                    "device": did, "metric": m, "z": round(z, 2),
                    "value": round(value, 2), "status": "open",
                    "opened_at": t, **diag,
                })
                del state["incidents"][50:]
                state["devices"][did]["status"] = "incident"
            elif active and abs(z) < Z_RELEASE:
                active["status"] = "resolved"
                active["resolved_at"] = t
        if not any(i["device"] == did and i["status"] == "open" for i in state["incidents"]):
            state["devices"][did]["status"] = "healthy"


async def tick_loop() -> None:
    while True:
        tick()
        await asyncio.sleep(TICK_SECONDS)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    asyncio.create_task(tick_loop())
    yield


app = FastAPI(title="VoltGuard", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.get("/api/state")
async def api_state() -> JSONResponse:
    return JSONResponse(state)


@app.get("/")
async def dashboard() -> FileResponse:
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), log_level="warning")
