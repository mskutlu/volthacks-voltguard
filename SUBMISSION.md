Devpost submission kit + demo script
====================================

DEADLINE: Sep 05, 2026 — submit at https://volthacks.devpost.com/

--------------------------------------------------
1. Devpost submission copy (paste into the form)
--------------------------------------------------

Project name: VoltGuard

Project tagline:
An AI ops copilot that watches IoT energy fleets and turns anomalies into
plain-English diagnoses and fix-it actions — before a human would even notice.

Short description (≤ 300 chars):
Home batteries and solar inverters fail quietly. VoltGuard streams telemetry
from every device, detects anomalies with rolling z-scores, and writes each
incident up with a root cause and a concrete remediation step — Gemini when a
key is present, a deterministic rule engine when it's not. One command to run.

Inspiration:
Every IoT ops team has the same 3 a.m. problem: dashboards full of charts,
nobody watching them, and failures that announce themselves only after
damage. We wanted the dashboard to do the watching — and to talk like an
engineer, not an alertID.

What it does:
- Simulates an 8-device energy fleet (home batteries + solar inverters)
  streaming voltage, temperature, and load at 1 Hz.
- Detects anomalies with an explainable rolling z-score (2-strike rule) per
  device per metric — no black-box model, thresholds you can audit.
- On detection, writes an incident: root-cause diagnosis + one concrete
  remediation action + severity. Diagnosis uses Gemini 2.0 Flash when
  GEMINI_API_KEY is set, and falls back to a deterministic rule engine so the
  product never goes dark (the active "brain" is shown in the UI).
- Live dashboard: fleet cards with canvas sparklines, per-metric z-scores,
  and a rolling AI incident feed. Single static file, no build step.

How we built it:
Python + FastAPI single-file backend (simulator, detector, diagnosis, API),
vanilla JS/canvas dashboard, stdlib urllib for the Gemini REST call, uv
inline script metadata so `uv run server.py` installs and runs everything.
Dockerfile included for one-container deploys.

Challenges we ran into:
Making the AI path resilient: LLM APIs rate-limit and keys expire, so an
ops tool that depends on them is fragile. The rule-engine fallback keeps
diagnosis available 100% of the time and makes the LLM an upgrade, not a
dependency.

Accomplishments we're proud of:
Whole product runs with one command and zero accounts; every anomaly the
detector fires ships with an actionable sentence a non-engineer understands.

What we learned:
Explainability beats model size in ops tooling — a z-score with a two-strike
rule is debuggable in a way a neural net isn't, and pairing it with an LLM
gives you both trust and fluency.

What's next for VoltGuard:
Real MQTT device ingestion, persistent incident history, and
acknowledge/escalation workflows with on-call routing.

Built with: python, fastapi, gemini, javascript, canvas, docker, uv

Try it (required links section):
- GitHub repo: <OWNER: push repo, paste URL>
- Live demo: <OWNER: deploy or record — Dockerfile provided>
- Demo video: <OWNER: record per script below>

--------------------------------------------------
2. 3-minute demo video script
--------------------------------------------------

Screen-record the dashboard at http://localhost:8000 (run `uv run server.py`
~5 minutes before recording so baseline stats exist, and optionally export
GEMINI_API_KEY for live AI diagnoses).

0:00–0:20 — Problem. "IoT energy fleets fail quietly. Dashboards are full of
charts; nobody watches them. This is VoltGuard — the dashboard that watches
itself and talks like an ops engineer."
0:20–0:40 — Show the fleet: 8 devices, live sparklines, healthy badges.
Point at the voltage/temperature/load tiles.
0:40–1:20 — Wait for (or wait out) a fault. When a card goes red: show the
z-score jump on the sparkline, then the incident appearing in the feed:
diagnosis, severity, recommended action. Read one aloud.
1:20–2:00 — Explain the pipeline in one breath: telemetry -> rolling
z-score detector (two-strike rule) -> diagnosis -> action. Show README
architecture section briefly. Emphasize the rule-engine fallback and the
"AI: <brain>" badge.
2:00–2:30 — If Gemini is enabled: contrast a Gemini diagnosis vs rule-engine
output. If not: show GEMINI_API_KEY env line and say "drop in a key, the LLM
takes over diagnosis; without it the rule engine never goes dark."
2:30–3:00 — Wrap: "One command to run, no accounts, no keys required.
VoltGuard — your fleet's first responder." Show the repo/README.

Recording tips: 1080p, zoom browser to 125%, keep incidents panel visible.
If no fault fires within 2 minutes, restart the server — it seeds fresh.

--------------------------------------------------
3. Owner action checklist (what only a human can do)
--------------------------------------------------

[ ] 1. Push this repo to GitHub (public) — no git remote exists in the agent
       workspace. `git remote add origin <url> && git push -u origin volthacks-entry`
[ ] 2. Create/register a Devpost account and click "Join hackathon" at
       https://volthacks.devpost.com/ before the deadline.
[ ] 3. Submit the entry with the copy in section 1 + repo URL + screenshots
       (dashboard healthy view + one incident view).
[ ] 4. Record the 3-min video (script above), upload to YouTube (public or
       unlisted), paste link into the Devpost form.
[ ] 5. Optional: GEMINI_API_KEY from https://aistudio.google.com/apikey —
       only if you want live LLM diagnoses in the recording. Not required.
[ ] 6. Optional: deploy somewhere public (Fly.io/Render/GCP Cloud Run all
       take the included Dockerfile) and paste the URL as live demo.
