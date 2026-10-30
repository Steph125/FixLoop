from fakes import FakeAgent, FakeMemory, FakeOutput, RaisingAgent, UnknownAgent

from fixloop.geometry import measure
from fixloop.procedures import load_all
from fixloop.sim import frame
from fixloop.state_machine import Session, State

PROCS = load_all()


class Runner:
    def __init__(self, agent=None, **session_kw):
        self.agent, self.memory, self.out = agent or FakeAgent(), FakeMemory(), FakeOutput()
        self.s = Session(PROCS, self.agent, self.memory, self.out, bike_id="velo-test", **session_kw)
        self.i = 0
        self.s.start(images=[])

    def feed(self, kind, n, dt=0.5):
        for _ in range(n):
            fm = frame(kind, self.i, self.i * dt)
            self.s.on_measures(measure(fm, self.s.procedure))
            self.i += 1

    def events(self, name):
        return [e for e in self.s.log if e["event"] == name]


def test_happy_path_to_closure():
    r = Runner()
    r.feed("off", 4)                      # étape 1 : pièces visibles
    assert r.s.step["id"] == "engage_top_teeth"
    r.feed("off", 6)                      # chaîne encore tombée : pas d'alerte avant « c'est fait »
    assert r.s.state == State.OBSERVATION and not r.events("anomaly")
    r.feed("on", 4)                       # chaîne posée
    assert r.s.step["id"] == "turn_backward"
    r.feed("on", 6)                       # demande « c'est fait »
    assert r.s.step["id"] == "turn_backward"
    r.s.on_user_done()
    r.feed("on", 4)
    assert r.s.state == State.ESSAI_DYNAMIQUE
    r.feed("on", 8)                       # 3,5 s de rotation stable
    assert r.s.state == State.CLOTURE
    assert r.memory.saved and r.memory.saved[0]["success"]
    assert r.s.model_calls == {"spark": 1, "wonder": 2}


def test_anomaly_then_correction():
    r = Runner()
    r.feed("off", 4)
    r.s.on_user_done()
    r.feed("off", 4)                      # « c'est fait » mais chaîne toujours tombée
    assert len(r.events("anomaly")) == 1 and "explain" in r.agent.calls
    assert (("chain",), "red") in r.out.highlights
    r.feed("on", 4)
    assert r.s.step["id"] == "turn_backward"


def test_uncertain_asks_spark_once_then_geometry_decides():
    r = Runner(FakeAgent(arbitrate_to="0"))
    r.feed("off", 4)
    r.s.on_user_done()
    r.feed("hidden", 12)                  # 6 s main devant la chaîne : Spark appelé une seule fois
    assert r.agent.calls.count("arbitrate") == 1
    assert "Montre-moi le plateau de face." in r.out.said
    assert r.s.step["id"] == "engage_top_teeth"   # Spark ne valide pas
    r.feed("on", 4)                       # la mesure SAM confirme
    assert r.s.step["id"] == "turn_backward"


def test_spark_confirmed_failure_triggers_explanation():
    r = Runner(FakeAgent(arbitrate_to="eps"))
    r.feed("off", 4)
    r.s.on_user_done()
    r.feed("hidden", 4)
    assert r.events("anomaly") and "explain" in r.agent.calls


def test_dynamic_failure_returns_to_last_step():
    r = Runner()
    r.feed("off", 4); r.feed("on", 4); r.s.on_user_done(); r.feed("on", 4)
    assert r.s.state == State.ESSAI_DYNAMIQUE
    r.feed("off", 4)                      # la chaîne saute pendant la rotation
    assert r.s.state == State.OBSERVATION and r.s.step["id"] == "turn_backward"
    assert r.events("anomaly")


def test_session_debounce_3_validates_after_3_frames():
    r = Runner(debounce_frames=3)
    r.feed("off", 3)                      # CORE-R3.8 : N de session (3 en direct)
    assert r.s.step["id"] == "engage_top_teeth"
    r.feed("on", 3)
    assert r.s.step["id"] == "turn_backward"
    r2 = Runner()                         # défaut : 4 en replay (CORE-R9.1)
    r2.feed("off", 3)
    assert r2.s.step["id"] == "frame_view"


def test_raising_agent_still_reaches_closure():
    r = Runner(agent=RaisingAgent())
    assert r.s.procedure["id"] == "chain_off_chainring"  # repli : 1re fiche
    r.feed("off", 4)
    assert r.s.step["id"] == "engage_top_teeth"
    r.s.on_user_done()
    r.feed("off", 4)                      # anomalie : message de la règle dit (CORE-R5.4)
    assert len(r.events("anomaly")) == 1
    assert any("pas encore sur les dents" in s for s in r.out.said)
    r.s.on_user_done()
    r.feed("hidden", 4)                   # incertain : arbitrage muet, conseil par défaut (CORE-R7.4)
    assert any("Montre-moi le plateau de face" in s for s in r.out.said)
    assert r.s.step["id"] == "engage_top_teeth"   # jamais validé par l'agent
    r.feed("on", 4)
    assert r.s.step["id"] == "turn_backward"
    r.s.on_user_done()
    r.feed("on", 4)
    assert r.s.state == State.ESSAI_DYNAMIQUE
    r.feed("on", 8)
    assert r.s.state == State.CLOTURE


def test_unknown_procedure_falls_back_to_first():
    r = Runner(agent=UnknownAgent())
    assert r.s.procedure["id"] == "chain_off_chainring"


def test_out_of_order_measures_are_ignored():
    r = Runner()
    r.feed("off", 4)
    assert r.s.step["id"] == "engage_top_teeth" and r.s.window == []
    old = measure(frame("off", 99, 0.1), r.s.procedure)   # t inférieur : ignorée
    r.s.on_measures(old)
    assert r.s.window == [] and r.s.step["id"] == "engage_top_teeth"


def test_measures_ignored_after_closure():
    r = Runner()
    r.feed("off", 4); r.feed("on", 4); r.s.on_user_done(); r.feed("on", 4)
    r.feed("on", 8)
    assert r.s.state == State.CLOTURE
    n_events = len(r.s.log)
    r.s.on_measures(measure(frame("on", 999, 999.0), r.s.procedure))
    assert r.s.state == State.CLOTURE and len(r.s.log) == n_events


def test_anomaly_is_not_repeated_during_cooldown():
    r = Runner()
    r.feed("off", 4); r.feed("on", 4)     # étape turn_backward
    r.feed("off", 12)                     # 6 s chaîne tombée : une seule alerte (anti-répétition 8 s)
    assert len(r.events("anomaly")) == 1
    r.feed("off", 10)                     # au-delà de 8 s : rappel
    assert len(r.events("anomaly")) == 2
