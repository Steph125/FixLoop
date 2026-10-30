import math

from fixloop.geometry import contact_ratio, measure
from fixloop.procedures import load_all
from fixloop.sim import frame
from fixloop.verifier import verify

PROC = load_all()["chain_off_chainring"]
STEP_ENGAGE = PROC["steps"][1]


def m(kind, i=0):
    return measure(frame(kind, i, i * 0.5), PROC)


def test_contact_ratio_separates_on_and_off():
    # mêmes ordres de grandeur que la vraie vidéo : en place ~0,09, tombée ~0,34
    on = m("on").contact[("chain", "chainring")]
    off = m("off").contact[("chain", "chainring")]
    assert on <= 0.18 and off >= 0.26


def test_missing_part_gives_nan():
    assert math.isnan(m("hidden").contact[("chain", "chainring")])
    assert math.isnan(contact_ratio(None, None))


def test_not_enough_frames_is_in_progress():
    assert verify(STEP_ENGAGE, [m("on")] * 3, user_done=False).value == "0"


def test_success_after_debounce():
    assert verify(STEP_ENGAGE, [m("on")] * 4, user_done=False).value == "1"


def test_initial_state_is_not_an_anomaly_before_done():
    assert verify(STEP_ENGAGE, [m("off")] * 6, user_done=False).value == "0"


def test_anomaly_after_done():
    v = verify(STEP_ENGAGE, [m("off")] * 4, user_done=True)
    assert v.value == "eps" and "plateau" in v.message


def test_uncertain_when_done_but_chain_hidden():
    assert verify(STEP_ENGAGE, [m("hidden")] * 4, user_done=True).value == "?"


def test_flicker_does_not_validate():
    window = [m("on"), m("on"), m("hidden"), m("on")]
    assert verify(STEP_ENGAGE, window, user_done=False).value == "0"


def test_requires_done():
    step = PROC["steps"][2]
    assert verify(step, [m("on")] * 6, user_done=False).value == "0"
    assert verify(step, [m("on")] * 6, user_done=True).value == "1"
