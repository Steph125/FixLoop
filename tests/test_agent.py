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
        return types.SimpleNamespace(output_text=self.answer)


def test_extract_json_tolerates_fences_and_text():
    assert extract_json('Voici : ```json\n{"a": 1}\n``` fin') == {"a": 1}
    assert extract_json("pas de json") is None


def test_diagnose_picks_known_procedure_and_sends_images():
    c = FakeClient('{"procedure": "chain_off_chainring", "raison": "chaîne pendante"}')
    agent = SparkAgent(PROCS, client=c)
    assert agent.diagnose([IMG, IMG], PROCS, "aucun") == "chain_off_chainring"
    content = c.sent[0]["input"][0]["content"]
    assert sum(p["type"] == "input_image" for p in content) == 2
    assert c.sent[0]["model"] == "muse-spark-1.3"


def test_diagnose_falls_back_on_unknown_id():
    agent = SparkAgent(PROCS, client=FakeClient('{"procedure": "inventee"}'))
    assert agent.diagnose([IMG], PROCS, "") == "chain_off_chainring"


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
