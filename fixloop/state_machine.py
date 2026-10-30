"""Machine à états de FixLoop (spec/01-core-loop/design.md, section 6).

Logique pure, sans appel réseau : les modèles Meta sont injectés via `Agent` et `Memory`,
la sortie vers le téléphone via `Output`. Les tests et la simulation passent des faux objets.
"""

from __future__ import annotations

from collections import deque
from enum import Enum
from typing import Any, Protocol

from .models import Measures, Verdict
from .verifier import holds, verify


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


DEFAULT_ADVICE = "Je ne vois pas bien. Montre-moi le plateau de face, mains hors du champ."
FALLBACK_PROBLEM = "Il y a un problème, regarde la pièce en rouge."
PART_FRENCH = {"chain": "la chaîne", "chainring": "le plateau", "derailleur": "le dérailleur"}
FRAMING_COOLDOWN_S = 10.0


class Session:
    def __init__(self, procedures: dict[str, dict], agent: Agent, memory: Memory, out: Output,
                 bike_id: str, anomaly_cooldown_s: float = 8.0, keyframes_kept: int = 3,
                 arbitration_cooldown_s: float = 10.0, debounce_frames: int = 4,
                 framing_timeout_s: float = 6.0):
        self.procedures, self.agent, self.memory, self.out = procedures, agent, memory, out
        self.bike_id = bike_id
        self.debounce_frames = debounce_frames  # 3 en direct, 4 en replay (CORE-R9.1)
        self.framing_timeout_s = framing_timeout_s
        self.last_seen: dict[str, float] = {}
        self.next_framing_t = -1.0
        self.cooldown = anomaly_cooldown_s
        self.arbitration_cooldown = arbitration_cooldown_s
        self.next_arbitration_t = -1.0
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
        try:
            proc_id = self.agent.diagnose(images, self.procedures, history)
        except Exception:
            proc_id = None
        self.model_calls["spark"] += 1
        if proc_id not in self.procedures:  # inconnu ou agent muet : 1re fiche
            proc_id = next(iter(self.procedures))
        self.procedure = self.procedures[proc_id]
        self._event("diagnose", procedure=proc_id)
        self._enter_step(0)

    def on_user_done(self) -> None:
        if self.state in (State.OBSERVATION, State.ESSAI_DYNAMIQUE):
            self.user_done = True
            self._event("user_done")

    def on_measures(self, m: Measures, keyframe: Any = None) -> None:
        if self.state == State.CLOTURE:
            return
        if m.t < self.t:  # arrivée hors ordre : ignorée (le serveur livre dans le désordre)
            return
        self.t = m.t
        if keyframe is not None:
            self.keyframes.append(keyframe)
        for part, seen in m.detected.items():
            if seen:
                self.last_seen[part] = m.t
        if self.state == State.OBSERVATION:
            self.window.append(m)
            if self._check_step() is not None:  # verdict discret : on peut signaler le cadrage
                self._check_framing()
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

    def _check_step(self) -> Verdict | None:
        """Rend le verdict s'il est discret (`0`), sinon None (quelque chose a été dit)."""
        v = verify(self.step, self.window, self.user_done, self.debounce_frames)
        if v.value == "eps" and self._suppressed(v):
            return None
        if v.value == "?":
            if self.t < self.next_arbitration_t:   # Spark au plus une fois toutes les 10 s
                return None
            self.state = State.ARBITRAGE
            try:
                v = self.agent.arbitrate(self.step, list(self.keyframes),
                                         self.window[-self.debounce_frames:])
            except Exception:
                v = None
            self.model_calls["spark"] += 1
            v = self._safe_arbitration(v)
            self.next_arbitration_t = self.t + self.arbitration_cooldown
            self._event("arbitrate", verdict=v.value, evidence=v.evidence)
            if v.value == "0":
                self.out.say(v.message or DEFAULT_ADVICE)
        if v.value == "1":
            self._validate(v)
            return None
        if v.value == "eps":
            self._anomaly(v)
            return None
        if self.state == State.ARBITRAGE:
            self.state = State.OBSERVATION
            return None
        return v  # "0" discret

    def _required_parts(self) -> list[str]:
        """Pièces citées par les règles de succès de l'étape en cours (CORE-R10)."""
        parts = []
        for rule in self.step.get("success", []):
            for key in ("part", "a", "b"):
                if key in rule and rule[key] not in parts:
                    parts.append(rule[key])
        return parts

    def _check_framing(self) -> None:
        """Perte du cadrage : pièce requise invisible depuis `framing_timeout_s` (CORE-R10)."""
        if self.t < self.next_framing_t:
            return
        for part in self._required_parts():
            if self.t - self.last_seen.get(part, 0.0) >= self.framing_timeout_s:
                self.out.say(f"Je ne vois plus {PART_FRENCH.get(part, part)}. "
                             "Replace le téléphone face au plateau.")
                self._event("framing_lost", part=part)
                self.next_framing_t = self.t + FRAMING_COOLDOWN_S
                return

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

    @staticmethod
    def _safe_arbitration(v: Any) -> Verdict:
        """Un arbitrage ne valide jamais : `eps` ou `0`, sinon repli (CORE-R7.5, AGT-R2)."""
        if isinstance(v, Verdict) and v.value in ("eps", "0"):
            return v
        evidence = getattr(v, "evidence", None) if isinstance(v, Verdict) else None
        evidence = dict(evidence) if isinstance(evidence, dict) else {}
        evidence["ignore"] = "Spark ne valide jamais : on attend que la mesure SAM confirme"
        message = getattr(v, "message", None) if isinstance(v, Verdict) else None
        return Verdict("0", None, evidence, message or DEFAULT_ADVICE)

    def _anomaly(self, v: Verdict) -> None:
        self.state = State.ANOMALIE
        try:
            text, part = self.agent.explain(self.step, v, list(self.keyframes))
        except Exception:
            text, part = None, None
        self.model_calls["spark"] += 1
        if not isinstance(text, str) or not text:
            text = v.message or FALLBACK_PROBLEM  # CORE-R5.4 : agent muet, message de la règle
        if not isinstance(part, str) or part not in self.procedure.get("parts", {}):
            part = None
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
        if self.fail_streak >= self.debounce_frames:
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
