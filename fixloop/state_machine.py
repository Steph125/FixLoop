"""Machine à états de FixLoop (spec/state_machine.md).

Logique pure, sans appel réseau : les modèles Meta sont injectés via `Agent` et `Memory`,
la sortie vers le téléphone via `Output`. Les tests et la simulation passent des faux objets.
"""

from __future__ import annotations

from collections import deque
from enum import Enum
from typing import Any, Protocol

from .models import Measures, Verdict
from .verifier import DEFAULT_DEBOUNCE, holds, verify


class State(str, Enum):
    DEMARRAGE = "DEMARRAGE"
    OBSERVATION = "OBSERVATION"
    ARBITRAGE = "ARBITRAGE"
    ANOMALIE = "ANOMALIE"
    ETAPE_VALIDEE = "ETAPE_VALIDEE"
    ESSAI_DYNAMIQUE = "ESSAI_DYNAMIQUE"
    CLOTURE = "CLOTURE"


class Agent(Protocol):  # Muse Spark
    def diagnose(self, images: list[Any], procedures: dict[str, dict], history: str) -> str: ...
    def arbitrate(self, step: dict, keyframes: list[Any], window: list[Measures]) -> Verdict: ...
    def explain(self, step: dict, verdict: Verdict, keyframes: list[Any]) -> tuple[str, str | None]: ...


class Memory(Protocol):  # Muse Wonder
    def load(self, bike_id: str) -> str: ...
    def save(self, bike_id: str, report: dict) -> None: ...


class Output(Protocol):  # téléphone
    def say(self, text: str) -> None: ...
    def highlight(self, parts: list[str], color: str) -> None: ...


class Session:
    def __init__(self, procedures: dict[str, dict], agent: Agent, memory: Memory, out: Output,
                 bike_id: str, anomaly_cooldown_s: float = 8.0, keyframes_kept: int = 3):
        self.procedures, self.agent, self.memory, self.out = procedures, agent, memory, out
        self.bike_id = bike_id
        self.cooldown = anomaly_cooldown_s
        self.state = State.DEMARRAGE
        self.procedure: dict | None = None
        self.k = 0
        self.window: list[Measures] = []
        self.user_done = False
        self.keyframes: deque = deque(maxlen=keyframes_kept)
        self.suppressed: dict[str, float] = {}       # message d'anomalie -> réactivé à t
        self.dynamic_t0: float | None = None
        self.fail_streak = 0
        self.model_calls = {"spark": 0, "wonder": 0}
        self.log: list[dict] = []
        self.t = 0.0

    # ------------------------------------------------------------------ entrées
    def start(self, images: list[Any]) -> None:
        history = self.memory.load(self.bike_id)
        self.model_calls["wonder"] += 1
        proc_id = self.agent.diagnose(images, self.procedures, history)
        self.model_calls["spark"] += 1
        self.procedure = self.procedures[proc_id]
        self._event("diagnose", procedure=proc_id)
        self._enter_step(0)

    def on_user_done(self) -> None:
        if self.state in (State.OBSERVATION, State.ESSAI_DYNAMIQUE):
            self.user_done = True
            self._event("user_done")

    def on_measures(self, m: Measures, keyframe: Any = None) -> None:
        self.t = m.t
        if keyframe is not None:
            self.keyframes.append(keyframe)
        if self.state == State.OBSERVATION:
            self.window.append(m)
            self._check_step()
        elif self.state == State.ESSAI_DYNAMIQUE:
            self.window.append(m)
            self._check_dynamic()

    # ------------------------------------------------------------------ logique
    @property
    def step(self) -> dict:
        return self.procedure["steps"][self.k]

    def _enter_step(self, k: int) -> None:
        self.k, self.window, self.user_done = k, [], False
        self.state = State.OBSERVATION
        self.out.say(self.step["instruction"])
        self.out.highlight(self.step.get("highlight", []), "blue")
        self._event("step", step=self.step["id"])

    def _check_step(self) -> None:
        v = verify(self.step, self.window, self.user_done)
        if v.value == "eps" and self._suppressed(v):
            return
        if v.value == "?":
            self.state = State.ARBITRAGE
            v = self.agent.arbitrate(self.step, list(self.keyframes), self.window[-DEFAULT_DEBOUNCE:])
            self.model_calls["spark"] += 1
            self._event("arbitrate", verdict=v.value)
        if v.value == "1":
            self._validate(v)
        elif v.value == "eps":
            self._anomaly(v)
        elif self.state == State.ARBITRAGE:
            self.state = State.OBSERVATION

    def _validate(self, v: Verdict) -> None:
        self.state = State.ETAPE_VALIDEE
        self._event("validated", step=self.step["id"], evidence=v.evidence)
        self.out.say("C'est bon.")
        if self.k + 1 < len(self.procedure["steps"]):
            self._enter_step(self.k + 1)
        elif "dynamic_test" in self.procedure:
            self._enter_dynamic()
        else:
            self._close(success=True)

    def _anomaly(self, v: Verdict) -> None:
        self.state = State.ANOMALIE
        text, part = self.agent.explain(self.step, v, list(self.keyframes))
        self.model_calls["spark"] += 1
        self.out.say(text)
        self.out.highlight([part] if part else self.step.get("highlight", []), "red")
        self._event("anomaly", step=self.step["id"], message=v.message, evidence=v.evidence)
        self.suppressed[v.message or ""] = self.t + self.cooldown
        self.window, self.user_done = [], False
        self.state = State.OBSERVATION

    def _suppressed(self, v: Verdict) -> bool:
        return self.t < self.suppressed.get(v.message or "", -1.0)

    def _enter_dynamic(self) -> None:
        self.state = State.ESSAI_DYNAMIQUE
        self.window, self.dynamic_t0, self.fail_streak = [], None, 0
        self.out.say(self.procedure["dynamic_test"]["instruction"])
        self._event("dynamic_start")

    def _check_dynamic(self) -> None:
        test = self.procedure["dynamic_test"]
        m = self.window[-1]
        if holds(test["must_hold"], [m]):
            self.fail_streak = 0
            if self.dynamic_t0 is None:
                self.dynamic_t0 = m.t
            if m.t - self.dynamic_t0 >= test["duration_s"]:
                self._close(success=True)
            return
        self.dynamic_t0 = None          # on recompte depuis la prochaine image correcte
        self.fail_streak += 1
        if self.fail_streak >= DEFAULT_DEBOUNCE:
            v = Verdict("eps", test["must_hold"][0], {"frame": m.frame_index},
                        "La chaîne n'est pas restée en place pendant la rotation.")
            self.k = len(self.procedure["steps"]) - 1   # on reprend à la dernière étape
            self._anomaly(v)
            self.out.say(self.step["instruction"])

    def _close(self, success: bool) -> None:
        self.state = State.CLOTURE
        report = {"procedure": self.procedure["id"], "success": success,
                  "events": [e for e in self.log if e["event"] in ("validated", "anomaly")],
                  "model_calls": dict(self.model_calls)}
        self.memory.save(self.bike_id, report)
        self.model_calls["wonder"] += 1
        self.out.say("Réparation validée. Je l'ai ajoutée à l'historique de ton vélo.")
        self._event("closed", success=success)

    def _event(self, event: str, **data) -> None:
        self.log.append({"t": round(self.t, 2), "event": event, "state": self.state.value,
                         "model_calls": dict(self.model_calls), **data})
