"""Chapter 10: who could have opened the door. First docstring lines are `make exercise`'s list."""

import pytest

from lantern import case

LOG = case.read("badge-log.csv")
OVERRIDES = {
    "OVR-MNT-01": {"holder": "the lift maintenance contractor", "valid": ("08:00", "18:00")},
    "OVR-AUD-02": {"holder": "Brightwater & Co", "valid": None},
}
ALIBIS = {
    "T. Reyes": "inside the stairwell from 23:13",
    "R. Malhotra": None,
    "E. Voss": "at the Harbour Hotel dinner",
    "I. Petrov": "on the hut camera 23:29:50 to 23:44:12",
}
HEADER = "time,badge_id,holder,door,direction,result\n"


def night(impl):
    return impl.door_candidates(LOG, door="STAIR-C-BOTTOM", at="23:36:15", overrides=OVERRIDES,
                                alibis=ALIBIS)


def test_the_credential_comes_from_the_log(impl):
    """The 23:36:15 entry through STAIR-C-BOTTOM was made with OVR-AUD-02."""
    assert night(impl)["credential"] == "OVR-AUD-02", "read badge_id from the matching log row"


def test_brightwater_could_and_malhotra_is_not_ruled_out(impl):
    """Brightwater held the code that opened it; Malhotra has no alibi, so he stays open."""
    out = night(impl)
    assert out["could"] == ["Brightwater & Co"], f"only the holder of OVR-AUD-02 could: {out}"
    assert out["not_ruled_out"] == ["R. Malhotra"], (
        "Malhotra did not hold the code, but nothing places him elsewhere at 23:36"
    )


def test_the_lift_contractor_is_ruled_out_by_the_code(impl):
    """The lift contractor is ruled out, with a reason naming OVR-MNT-01 and its 18:00 limit."""
    reason = night(impl)["ruled_out"].get("the lift maintenance contractor", "")
    assert "OVR-MNT-01" in reason and "18:00" in reason, f"reason given: {reason!r}"


def test_people_with_an_alibi_are_ruled_out_by_it(impl):
    """Reyes, Voss and Petrov are ruled out, each with their own alibi as the reason."""
    out = night(impl)["ruled_out"]
    for person in ("T. Reyes", "E. Voss", "I. Petrov"):
        assert out.get(person) == ALIBIS[person], f"{person}: use the alibi as the reason"


def test_a_code_outside_its_hours_rules_its_holder_out(impl):
    """An entry with OVR-MNT-01 at 23:36 does not make the lift contractor a candidate."""
    log = HEADER + "23:36:15,OVR-MNT-01,override code,STAIR-C-BOTTOM,in,granted\n"
    out = impl.door_candidates(log, door="STAIR-C-BOTTOM", at="23:36:15", overrides=OVERRIDES,
                               alibis={})
    assert out["could"] == [], f"the code was not valid at 23:36: {out}"
    assert "18:00" in out["ruled_out"]["the lift maintenance contractor"]


def test_a_code_inside_its_hours_makes_its_holder_a_candidate(impl):
    """The same code at 10:00, inside its hours, makes the lift contractor a candidate."""
    log = HEADER + "10:00:00,OVR-MNT-01,override code,STAIR-C-BOTTOM,in,granted\n"
    out = impl.door_candidates(log, door="STAIR-C-BOTTOM", at="10:00:00", overrides=OVERRIDES,
                               alibis={})
    assert out["could"] == ["the lift maintenance contractor"], out


def test_a_badge_entry_names_the_badge_holder(impl):
    """An entry made with a badge puts that badge's holder in `could`, even with no alibi entry."""
    log = HEADER + "23:40:00,B-0733,R. Malhotra,STAIR-C-BOTTOM,in,granted\n"
    out = impl.door_candidates(log, door="STAIR-C-BOTTOM", at="23:40:00", overrides=OVERRIDES,
                               alibis=ALIBIS)
    assert out["credential"] == "B-0733" and out["could"] == ["R. Malhotra"], out
    assert "R. Malhotra" not in out["not_ruled_out"], "a candidate is not also 'not ruled out'"


def test_no_matching_entry_is_an_error(impl):
    """Asking about a time with no entry raises ValueError instead of guessing."""
    with pytest.raises(ValueError):
        impl.door_candidates(LOG, door="STAIR-C-BOTTOM", at="23:40:00", overrides=OVERRIDES,
                             alibis=ALIBIS)
