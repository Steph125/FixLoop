# FixLoop — a repair agent that checks what you did

Point a phone at your bike drivetrain: FixLoop diagnoses a thrown chain, guides you step by step by
voice, and only moves on once it has **measured** the step is done. A failed step is refused out loud,
shown in red, and re-checked after you fix it.

[Replay online](TBD — deployment runs with RPL-T9) · [3 min video](TBD — filmed Nov 3) ·
[Benchmark](eval/benchmark) · [Spec](spec/README.md)

## What it does

Your chain fell off the chainring and tutorials cannot tell whether you put it back right. You prop up
your phone, and FixLoop validates each step from SAM 3.1 segmentation masks: framing, seating the chain
on the teeth, back-pedalling, then a 3 s spin test. Muse Spark explains errors but never validates.

## Why it's not an image analyzer

| An image analyzer | FixLoop |
|---|---|
| One image in, one answer out | A session with a state: card chosen, step `k/K`, measure history |
| The model says what it sees | A geometric measure on SAM masks decides; the language model never validates |
| No notion of success | Each step has measurable success and anomaly criteria, with debounce |
| No action | FixLoop acts: voice prompt, highlighted part, blocked progress, final test |
| No recovery | An anomaly triggers diagnosis, guided correction, re-verification |
| No proof | A benchmark on 20 clips compares 3 approaches (`eval/benchmark`) |

## How it works

```
phone camera → SAM 3.1 masks → contact ratio → verifier (0 / 1 / ? / eps)
     → state machine → voice + overlay → re-measure until the step holds
```

The contact ratio is the share of the chainring edge covered by the dilated chain mask (6 px edge,
6 px dilation). Chain seated: contact ≤ 0.18. Chain fallen: contact ≥ 0.26. Between the two, or when a
part is missing: uncertain. Source: `eval/day1/findings.md`.

```mermaid
stateDiagram-v2
    [*] --> Demarrage
    Demarrage --> Observation: card chosen (Spark)
    Observation --> Observation: V = 0
    state Verdict <<choice>>
    Observation --> Verdict: new measure
    Verdict --> EtapeValidee: V = 1 (SAM measure)
    Verdict --> Arbitrage: V = ? (at most once / 10 s)
    Verdict --> Anomalie: V = eps
    Arbitrage --> Observation: "0" doubt or ignored "pass" (Spark never validates)
    Arbitrage --> Anomalie: "fail", confidence >= 0.6
    Anomalie --> Observation: window cleared, same step
    state DerniereEtape <<choice>>
    EtapeValidee --> DerniereEtape
    DerniereEtape --> Observation: k < K
    DerniereEtape --> EssaiDynamique: k = K with test
    DerniereEtape --> Cloture: k = K without test
    EssaiDynamique --> Cloture: must_hold true for duration_s
    EssaiDynamique --> Anomalie: must_hold false on N frames
    Cloture --> [*]
```

## Meta models

| Model | ID | Role | Calling code | Proof of use |
|---|---|---|---|---|
| SAM 3.1 | `sam-3.1` | Segment chain, chainring (live image, replay video) | `fixloop/perception.py` | `eval/day1/findings.md` |
| Muse Spark | `muse-spark-1.3` | Initial diagnosis, failure arbitration, anomaly explanation | `fixloop/agent.py` | `eval/day2/findings.md` |
| Muse Wonder | `muse-wonder-1.0` | Bike history at start, closing report | `fixloop/memory.py` | `probe/` (preview API, background task) |
| Muse Voice Transcribe | `muse-voice-transcribe-1.0` | Hands-free commands ("c'est fait", "aide-moi") | `fixloop/voice.py`, `web/audio-worklet.js` | `probe/` (realtime transcription probe) |
| Muse Code | CLI `muse` | Built this project | — | `docs/muse-code-log.md` |

## Results

Measured on the author's bike (`eval/day1`, `eval/day2`). Benchmark numbers on 20 varied clips are
still being recorded: TBD (`eval/benchmark`).

| Measure | Value | Source |
|---|---|---|
| False validation (fallen chain judged seated) | 0 / 285 images | `eval/day1/findings.md` |
| Anomaly recall (fallen images flagged) | 78 / 78 | `eval/day1/findings.md` |
| Live verdict delay after a gesture, median (p90) | 1.9 s (4.4 s) | `eval/day1/findings.md` |
| Geometry cost per 848x464 image, median | 2.95 ms (target < 50 ms) | `eval/day1/findings.md` |
| Spark calls per session | TBD (not measured yet) | `eval/benchmark` |
| 3 min demo session cost | TBD (not measured yet) | `eval/benchmark` |
| Benchmark: false validations, 3 approaches | TBD (`eval/benchmark`) | `eval/benchmark` |

## Safety rule: Spark never validates

Muse Spark alone judged a fallen chain "passed" with 0.82 confidence (`eval/day2/findings.md`): the
bike's black guard disc looks like a seated chain to a generic description. So only the SAM geometry
measure can pass a step; Spark may confirm a failure, say it cannot see well, or explain.

## Try it

No bike, no key, no install: open the replay in a browser (link above once RPL-T9 is deployed) and
watch a full recorded session: refusal of a faked step, red contour, curve of the contact ratio, honest
banner showing the demo history. Live mode needs the author: server + phone on HTTPS, access code
on request.

## Run locally

Windows PowerShell, one command per line (Linux/macOS: same commands with `/` paths):

```
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # then paste your key
python scripts/check_setup.py
python -m pytest -q tests   # logic tests, no API call
python scripts/check_spec.py  # every criterion covered by a task
python scripts/benchmark.py --offline --fake  # benchmark on synthetic clips, no API call
```

A fresh clone must pass `pytest` by following only these steps (SUB-T4, due Nov 3).

## Built during the hackathon

| Date | What was built | Commits |
|---|---|---|
| Oct 28 | Environment check, SAM 3.1 probe, spec, first procedure, verifier + state machine | `git log --since 2026-10-26` |
| Oct 29 | First real SAM 3.1 measurements, calibrated thresholds | `eval/day1` |
| Oct 30 | Live image mode, Spark agent + safety rule, full spec | `eval/day2`, `spec/` |
| Oct 31 | Server, phone app, voice, memory, replay builder | `server/`, `web/`, `replay/` |
| Nov 1 | Benchmark + replay code without videos or API, deploy check (not run) | `scripts/benchmark.py`, `replay/deploy_check.py` |
| Nov 3 | README figures, 3 min video | TBD |
| Nov 4 | Freeze, public check, submission before 21:00 ET | `v1.0-submission` |

## Built with Muse Code

This project was written with Muse Code (Muse Spark backend): every prompt, produced file and
hand fix is journaled in [`docs/muse-code-log.md`](docs/muse-code-log.md). Spec first: no code without
a task in `spec/`, no task without tested acceptance criteria.

## Spec

[`spec/README.md`](spec/README.md) explains spec-driven development: EARS requirements, design, atomic
tasks. `python scripts/check_spec.py` checks that every acceptance criterion is covered by a task
(82 requirements, 299 criteria, 50 decisions, 104 tasks).

## License

MIT for the code in this repository. See [NOTICE.md](NOTICE.md) for third-party components
(package licenses copied from `pip show`, model terms, demo media).

