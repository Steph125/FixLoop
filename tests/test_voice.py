"""Détecteur de commandes vocales (spec/04-memory-voice, VOX-T2). Aucun réseau."""

from fixloop.voice import COMMANDS, CommandDetector, normalize


def test_normalize():
    assert normalize("C'est FAIT !") == "c est fait"  # VOX-R2.1
    assert normalize("Répète, s'il te plaît.") == "repete s il te plait"
    assert normalize("AIDE-MOI") == "aide moi"
    assert normalize("  quoi ?  ") == "quoi"


def test_each_listed_form_is_detected():
    expected = {"done": "done", "help": "help", "repeat": "repeat"}
    t = 0.0
    for cmd, forms in COMMANDS.items():
        for form in forms:
            det = CommandDetector()
            assert det.feed(form, t) == expected[cmd], form  # VOX-R2.1
            t += 3.0


def test_unknown_text_triggers_nothing():
    det = CommandDetector()
    assert det.feed("il fait beau aujourd'hui", 0.0) is None  # VOX-R2.2
    assert det.feed("", 1.0) is None


def test_whole_word_only():
    det = CommandDetector()
    assert det.feed("tu peux m'aider", 0.0) is None  # « aide » n'est pas « aider »
    assert det.feed("c'est infini", 1.0) is None  # « fini » n'est pas « infini »
    assert det.feed("pourquoi faire", 2.0) is None  # « quoi » n'est pas « pourquoi »
    assert det.feed("je prédis la suite", 3.0) is None


def test_priority_done_first():
    det = CommandDetector()
    assert det.feed("c'est fait, aide-moi", 0.0) == "done"  # VOX, design 2.2


def test_same_command_not_repeated_within_2s():
    det = CommandDetector()
    assert det.feed("fini", 0.0) == "done"
    assert det.feed("fini", 1.0) is None  # VOX-R2.3
    assert det.feed("fini", 2.1) == "done"


def test_muted_while_speaking_and_tail():
    det = CommandDetector()
    det.speaking(True, 0.0)
    assert det.feed("c'est fait", 1.0) is None  # VOX-R2.4 : FixLoop parle
    det.speaking(False, 2.0)
    assert det.feed("c'est fait", 2.2) is None  # 500 ms après la synthèse
    assert det.feed("c'est fait", 2.6) == "done"


def test_echo_phrase_ignored():
    det = CommandDetector()
    assert det.feed("Tu as dit que c'était fait, mais corrige.", 0.0) is None
