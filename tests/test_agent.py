import types

import numpy as np

from fixloop.agent import SparkAgent, extract_json
from fixloop.procedures import load_all

PROCS = load_all()
STEP = PROCS["chain_off_chainring"]["steps"][1]
IMG = np.zeros((100, 200, 3), np.uint8)


class FakeClient:
    """Imite client.responses.create et enregistre ce qui est envoyé."""

    def __init__(self, answer):
        self.answer, self.sent = answer, []
        self.responses = types.SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.sent.append(kw)
        if isinstance(self.answer, Exception):
            raise self.answer
        if hasattr(self.answer, "output_text"):  # reponse complete (avec usage) : telle quelle
            return self.answer
        return types.SimpleNamespace(output_text=self.answer)


def test_extract_json_tolerates_fences_and_text():
    assert extract_json('Voici : ```json\n{"a": 1}\n``` fin') == {"a": 1}
    assert extract_json("pas de json") is None


def test_diagnose_picks_known_procedure_and_sends_images():
    c = FakeClient('{"procedure": "chain_off_chainring", "raison": "chaîne pendante"}')
    agent = SparkAgent(PROCS, client=c)
    pid, raison = agent.diagnose([IMG, IMG], PROCS, "aucun")
    assert pid == "chain_off_chainring" and raison == "chaîne pendante"  # AGT-R1.4
    content = c.sent[0]["input"][0]["content"]
    assert sum(p["type"] == "input_image" for p in content) == 2
    assert c.sent[0]["model"] == "muse-spark-1.3"


def test_diagnose_falls_back_on_unknown_id():
    c = FakeClient('{"procedure": "inventee"}')
    agent = SparkAgent(PROCS, client=c)
    pid, raison = agent.diagnose([IMG], PROCS, "")
    assert pid == "chain_off_chainring" and raison is None  # AGT-R1.3 : 1re fiche, repli journalise
    assert any(e.get("fallback") for e in agent.calls if e.get("kind") == "diagnose")


def test_arbitrate_never_validates_but_confirms_failures():
    c = FakeClient('{"verdict": "reussie", "confiance": 0.95, "raison": "chaîne sur les dents"}')
    v = SparkAgent(PROCS, client=c).arbitrate(STEP, [IMG], [])
    assert v.value == "0" and "ignore" in v.evidence       # cas réel du 30 oct. : chaîne tombée jugée réussie
    prompt = c.sent[0]["input"][0]["content"][0]["text"]
    assert "fond la chaîne" in prompt and "disque noir" in prompt   # lecture inversée + repères du vélo
    assert SparkAgent(PROCS, client=FakeClient('{"verdict": "ratee", "confiance": 0.8}')).arbitrate(STEP, [IMG], []).value == "eps"
    assert SparkAgent(PROCS, client=FakeClient('{"verdict": "ratee", "confiance": 0.3}')).arbitrate(STEP, [IMG], []).value == "0"
    assert SparkAgent(PROCS, client=FakeClient("???")).arbitrate(STEP, [IMG], []).value == "0"


def test_unsure_answer_returns_filming_advice():
    c = FakeClient('{"verdict": "impossible_a_dire", "confiance": 0.8, "conseil": "Filme le plateau de face."}')
    v = SparkAgent(PROCS, client=c).arbitrate(STEP, [IMG], [])
    assert v.value == "0" and v.message == "Filme le plateau de face."


def test_network_error_never_blocks():
    agent = SparkAgent(PROCS, client=FakeClient(ConnectionError("coupé")))
    assert agent.arbitrate(STEP, [IMG], []).value == "0"
    from fixloop.models import Verdict
    text, part = agent.explain(STEP, Verdict("eps", message="Chaîne pas en place."), [IMG])
    assert text == "Chaîne pas en place." and part is None
    assert agent.calls[-1]["error"] == "ConnectionError"


def test_explain_returns_phrase_and_valid_part():
    from fixloop.models import Verdict
    c = FakeClient('{"phrase": "Remonte la chaîne sur les dents du haut.", "piece": "chain"}')
    text, part = SparkAgent(PROCS, client=c).explain(STEP, Verdict("eps", message="x"), [IMG])
    assert text.startswith("Remonte") and part == "chain"


def test_small_crop_is_not_upscaled():
    import base64
    import cv2
    from fixloop.agent import image_to_data_url
    small = np.zeros((200, 325, 3), np.uint8)
    data = base64.b64decode(image_to_data_url(small).split(",", 1)[1])
    assert cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR).shape[1] == 325


def test_reasoning_effort_is_sent():
    c = FakeClient('{"verdict": "ratee", "confiance": 0.9}')
    SparkAgent(PROCS, client=c).arbitrate(STEP, [IMG], [])
    assert c.sent[0]["reasoning"] == {"effort": "medium"}


def test_crop_around_box():
    from fixloop.agent import crop_around
    img = np.zeros((400, 800, 3), np.uint8)
    assert crop_around(img, (300, 100, 400, 200), margin=0.5).shape[:2] == (200, 200)


def test_low_confidence_failure_keeps_observing():
    from fixloop.agent import ACCEPT_FAILURE_CONF
    assert ACCEPT_FAILURE_CONF == 0.6
    borderline = FakeClient('{"verdict": "ratee", "confiance": 0.59, "raison": "doute"}')
    v = SparkAgent(PROCS, client=borderline).arbitrate(STEP, [IMG], [])
    assert v.value == "0"  # AGT-R2.4 : 0,59 < 0,6, on continue d'observer


def test_explain_truncates_long_phrase():
    from fixloop.models import Verdict
    long_ok = FakeClient('{"phrase": "Remonte la chaîne sur les dents du haut. Ensuite tu pourras tourner le pédalier doucement pour vérifier que tout tient bien en place.", "piece": "chain"}')
    text, part = SparkAgent(PROCS, client=long_ok).explain(STEP, Verdict("eps", message="Chaîne pas en place."), [IMG])
    assert text == "Remonte la chaîne sur les dents du haut."  # AGT-R4.5 : 1re phrase, 8 mots
    assert part == "chain"
    wordy = FakeClient('{"phrase": "' + " ".join(["mot"] * 25) + '. Suite.", "piece": "chain"}')
    text2, _ = SparkAgent(PROCS, client=wordy).explain(STEP, Verdict("eps", message="Chaîne pas en place."), [IMG])
    assert text2 == "Chaîne pas en place."  # 1re phrase trop longue : message de la règle


def test_help_returns_hint_and_falls_back_to_instruction():
    c = FakeClient('{"phrase": "Vise les dents du haut du plateau."}')
    hint = SparkAgent(PROCS, client=c).help(STEP, [IMG, IMG])
    assert hint == "Vise les dents du haut du plateau."  # AGT-R5.1 : une indication
    prompt = c.sent[0]["input"][0]["content"][0]["text"]
    assert "disque noir" in prompt  # visual_cues de la fiche
    assert c.sent[0]["reasoning"] == {"effort": "low"}
    mute = SparkAgent(PROCS, client=FakeClient("???"))
    assert mute.help(STEP, [IMG]) == STEP["instruction"]  # AGT-R5.2 : repli sur la consigne
    down = SparkAgent(PROCS, client=FakeClient(ConnectionError("coupé")))
    assert down.help(STEP, [IMG]) == STEP["instruction"]


class FakeCosts:
    """Capte les appels à CostLog.add sans écrire sur disque (AGT-T9)."""

    def __init__(self):
        self.entries = []

    def add(self, **kw):
        self.entries.append(kw)
        return 0.0


def test_spark_tokens_logged_and_reported_to_costs():
    import types

    costs = FakeCosts()
    resp = types.SimpleNamespace(
        output_text='{"verdict": "ratee", "confiance": 0.9}',
        usage=types.SimpleNamespace(input_tokens=1200, output_tokens=80))
    agent = SparkAgent(PROCS, client=FakeClient(resp), costs=costs)
    assert agent.arbitrate(STEP, [IMG, IMG], []).value == "eps"
    assert agent.calls[-1]["input_tokens"] == 1200  # AGT-R7.1 : jetons journalises
    assert agent.calls[-1]["output_tokens"] == 80
    billed = {(e["model"], e["kind"]): e for e in costs.entries}
    assert billed[("muse-spark-1.3", "in")]["units"] == 1200  # AGT-R7.2 : report dans les couts
    assert billed[("muse-spark-1.3", "out")]["units"] == 80
    assert not any(e.get("estimated") for e in costs.entries)


def test_spark_tokens_estimated_without_usage():
    costs = FakeCosts()
    agent = SparkAgent(PROCS, client=FakeClient('{"verdict": "ratee", "confiance": 0.9}'), costs=costs)
    agent.arbitrate(STEP, [IMG, IMG], [])
    assert agent.calls[-1]["input_tokens"] is None and agent.calls[-1]["output_tokens"] is None
    billed = {(e["model"], e["kind"]): e for e in costs.entries}
    assert billed[("muse-spark-1.3", "in")]["units"] == 2 * 1500  # 1 500 par image
    assert billed[("muse-spark-1.3", "out")]["units"] == 200
    assert all(e.get("estimated") for e in costs.entries)


def test_spark_calls_send_timeout_20_and_timeout_is_logged():
    from openai import APITimeoutError

    from fixloop.models import Verdict
    c = FakeClient('{"procedure": "chain_off_chainring", "raison": "chaine pendante"}')
    agent = SparkAgent(PROCS, client=c)
    assert agent.diagnose([IMG], PROCS, "aucun")[0] == "chain_off_chainring"
    assert c.sent[0].get("timeout") == 20  # AGT-R6.2 : delai maximal de 20 s
    c2 = FakeClient('{"verdict": "ratee", "confiance": 0.8}')
    agent2 = SparkAgent(PROCS, client=c2)
    agent2.arbitrate(STEP, [IMG], [])
    assert c2.sent[0].get("timeout") == 20
    agent2.explain(STEP, Verdict("eps", message="x"), [IMG])
    assert c2.sent[-1].get("timeout") == 20
    slow = FakeClient(APITimeoutError(request=None))
    agent3 = SparkAgent(PROCS, client=slow)
    assert agent3.arbitrate(STEP, [IMG], []).value == "0"  # delai traite comme absence de reponse
    assert agent3.calls[-1]["error"] == "APITimeoutError"
