"""Appli téléphone : vérifications statiques (spec/06-phone-app).

Aucun réseau, aucun navigateur : contrôle le HTML, le CSS et le JS livrés dans
`web/` (textes français, boutons exigés, sobriété APP-R10). La logique pure est
testée en JS dans `web/selftest.html` (miroir `web/selftest.mjs`, lancé par node).
"""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


def read(name):
    return (WEB / name).read_text(encoding="utf-8")


def test_required_files_exist():
    for name in ("index.html", "live.js", "style.css",
                 "lib.js", "selftest.html", "selftest.mjs"):
        assert (WEB / name).is_file(), f"web/{name} manquant"  # design 06, sections 1 et 7
    # audio-worklet.js arrive avec APP-T8 (voix en entrée)


def test_six_screens():
    html = read("index.html")
    found = re.findall(r'data-screen="([a-z]+)"', html)
    assert found == ["accueil", "cadrage", "session", "anomalie", "fin", "erreur"]  # APP-R8


def test_session_buttons_present():
    html = read("index.html")
    for label in ("C'est fait", "Aide", "Répète", "Pause"):
        assert label in html, f"bouton {label} manquant"  # APP-R4.2, écrans statiques
    assert "64" in read("style.css")  # hauteur de bouton, voir test_done_button_size


def test_done_button_size_in_css():
    css = read("style.css")
    assert "64px" in css  # APP-R4.1 : 64 px de haut
    assert "30%" in css or "min-width" in css  # au moins 30 % de la largeur


def test_text_sizes_and_contrast_in_css():
    css = read("style.css")
    assert "18px" in css  # APP-R9.2 : textes d'au moins 18 px
    assert "rgba" in css  # fond semi-opaque sur la vidéo (contraste 4,5:1)


def test_bike_id_and_access_code():
    live = read("live.js")
    assert "localStorage" in live  # APP-R6.1 : bike_id persisté
    assert "try" in live and "catch" in live  # lecture/écriture protégées
    assert "Historique non conservé" in live or "HISTORY_MESSAGE" in live  # APP-R6.2
    html = read("index.html")
    assert 'id="code"' in html  # APP-R1.5 : champ de code
    assert "/api/health" in live  # affiché si le serveur exige un code


def test_no_external_dependency_and_small_size():
    total = 0
    for name in ("index.html", "live.js", "style.css", "lib.js"):
        text = read(name)
        total += len(text.encode("utf-8"))
        assert 'src="http' not in text and "from 'http" not in text  # APP-R10.1
        assert 'from "http' not in text and "@import" not in text  # pas de bibliothèque
        assert "MODEL_API_KEY" not in text  # APP-R10.3 : jamais la clé API
    assert total < 100 * 1024  # APP-R10.2 : moins de 100 ko
