from fixloop.models import Verdict


class FakeAgent:
    def __init__(self, arbitrate_to="0"):
        self.calls, self.arbitrate_to = [], arbitrate_to

    def diagnose(self, images, procedures, history):
        self.calls.append("diagnose")
        return "chain_off_chainring"

    def arbitrate(self, step, keyframes, window):
        self.calls.append("arbitrate")
        msg = "Arbitrage : chaîne hors du plateau." if self.arbitrate_to == "eps" else "Montre-moi le plateau de face."
        return Verdict(self.arbitrate_to, None, {}, msg)

    def explain(self, step, verdict, keyframes):
        self.calls.append("explain")
        return (verdict.message or "Il y a un problème.", "chain")


class FakeMemory:
    def __init__(self):
        self.saved = []

    def load(self, bike_id):
        return "Aucune réparation enregistrée."

    def save(self, bike_id, report):
        self.saved.append(report)


class FakeOutput:
    def __init__(self):
        self.said, self.highlights = [], []

    def say(self, text):
        self.said.append(text)

    def highlight(self, parts, color):
        self.highlights.append((tuple(parts), color))
