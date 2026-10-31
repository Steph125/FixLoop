import asyncio
from types import SimpleNamespace

from fixloop.models import Verdict


class FakeAgent:
    def __init__(self, arbitrate_to="0"):
        self.calls, self.arbitrate_to = [], arbitrate_to

    def diagnose(self, images, procedures, history):
        self.calls.append("diagnose")
        return "chain_off_chainring", "La chaîne pend sous le plateau."

    def arbitrate(self, step, keyframes, window):
        self.calls.append("arbitrate")
        msg = "Arbitrage : chaîne hors du plateau." if self.arbitrate_to == "eps" else "Montre-moi le plateau de face."
        return Verdict(self.arbitrate_to, None, {}, msg)

    def explain(self, step, verdict, keyframes):
        self.calls.append("explain")
        return (verdict.message or "Il y a un problème.", "chain")

    def help(self, step, keyframes):
        self.calls.append("help")
        return "Aide : vise les dents du haut."


class RaisingAgent(FakeAgent):
    """Agent injoignable : chaque appel lève (spec/01-core-loop, CORE-T11)."""

    def diagnose(self, images, procedures, history):
        self.calls.append("diagnose")
        raise ConnectionError("diagnostic coupé")

    def arbitrate(self, step, keyframes, window):
        self.calls.append("arbitrate")
        raise TimeoutError("arbitrage coupé")

    def explain(self, step, verdict, keyframes):
        self.calls.append("explain")
        raise TimeoutError("explication coupée")

    def help(self, step, keyframes):
        self.calls.append("help")
        raise TimeoutError("aide coupée")


class UnknownAgent(FakeAgent):
    """Agent qui rend un identifiant de fiche inconnu."""

    def diagnose(self, images, procedures, history):
        self.calls.append("diagnose")
        return "n_existe_pas", None


class FakeMemory:
    def __init__(self):
        self.saved = []

    def load(self, bike_id):
        return "Aucune réparation enregistrée."

    def save(self, bike_id, report):
        self.saved.append(report)


class RaisingMemory(FakeMemory):
    """Memoire injoignable : `load` et `save` levent (spec/01-core-loop, CORE-T18)."""

    def load(self, bike_id):
        raise ConnectionError("historique coupe")

    def save(self, bike_id, report):
        raise ConnectionError("ecriture coupee")


class FakeSamStream:
    """Flux SAM rejoué : des événements texte qui portent une sortie brute valide."""

    def __init__(self, text):
        self.text = text
        self.closed = False

    def __aiter__(self):
        return self._events()

    async def _events(self):
        mid = len(self.text) // 2
        lane = {"output_index": 0, "content_index": 0, "item_id": "m"}
        yield {"type": "response.output_text.delta", "delta": self.text[:mid], **lane}
        yield {"type": "response.output_text.delta", "delta": self.text[mid:], **lane}
        yield {"type": "response.output_text.done", "text": self.text, **lane}
        yield {"type": "response.completed"}

    async def close(self):
        self.closed = True


class FakeSamClient:
    """Imite AsyncOpenAI pour sam-3.1 (spec/02-perception, PERC-T4).

    texts : prompt -> sortie brute SAM rejouée. failures : prompt -> liste
    d'exceptions levées par create() aux appels successifs (puis succès).
    gate : événement asyncio optionnel attendu dans chaque create().
    """

    def __init__(self, texts=None, failures=None, gate=None):
        self.texts = texts or {}
        self.failures = failures or {}
        self.gate = gate
        self.created = []
        self.calls = {}
        self.streams = []
        self.max_concurrent = 0
        self._concurrent = 0
        self.responses = SimpleNamespace(create=self._create)

    async def _create(self, **kw):
        prompt = kw["input"][0]["content"][0]["text"]
        self.created.append(kw)
        self.calls[prompt] = self.calls.get(prompt, 0) + 1
        self._concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self._concurrent)
        try:
            await asyncio.sleep(0)
            if self.gate is not None:
                await self.gate.wait()
        finally:
            self._concurrent -= 1
        seq = self.failures.get(prompt, [])
        if self.calls[prompt] <= len(seq):
            raise seq[self.calls[prompt] - 1]
        stream = FakeSamStream(self.texts.get(prompt, ""))
        self.streams.append(stream)
        return stream


class FakeOutput:
    def __init__(self):
        self.said, self.highlights, self.states = [], [], []

    def say(self, text):
        self.said.append(text)

    def highlight(self, parts, color):
        self.highlights.append((tuple(parts), color))

    def state(self, snapshot):
        self.states.append(snapshot)
