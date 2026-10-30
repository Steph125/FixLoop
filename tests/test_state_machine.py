from fakes import FakeAgent, FakeMemory, FakeOutput

from fixloop.geometry import measure
from fixloop.procedures import load_all
from fixloop.sim import frame
from fixloop.state_machine import Session, State

PROCS = load_all()


class Runner:
    def __init__(self, agent=None):
        self.agent, self.memory, self.out = agent or FakeAgent(), FakeMemory(), FakeOutput()
        self.s = Session(PROCS, self.agent, self.memory, self.out, bike_id="velo-test")
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


def test_uncertain_goes_to_arbitration():
    r = Runner(FakeAgent(arbitrate_to="1"))
    r.feed("off", 4)
    r.s.on_user_done()
    r.feed("hidden", 4)                   # main devant la chaîne
    assert "arbitrate" in r.agent.calls
    assert r.s.step["id"] == "turn_backward"


def test_dynamic_failure_returns_to_last_step():
    r = Runner()
    r.feed("off", 4); r.feed("on", 4); r.s.on_user_done(); r.feed("on", 4)
    assert r.s.state == State.ESSAI_DYNAMIQUE
    r.feed("off", 4)                      # la chaîne saute pendant la rotation
    assert r.s.state == State.OBSERVATION and r.s.step["id"] == "turn_backward"
    assert r.events("anomaly")


def test_anomaly_is_not_repeated_during_cooldown():
    r = Runner()
    r.feed("off", 4); r.feed("on", 4)     # étape turn_backward
    r.feed("off", 12)                     # 6 s chaîne tombée : une seule alerte (anti-répétition 8 s)
    assert len(r.events("anomaly")) == 1
    r.feed("off", 10)                     # au-delà de 8 s : rappel
    assert len(r.events("anomaly")) == 2
