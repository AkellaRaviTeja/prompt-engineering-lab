"""Chapter 09: the alibi check. Each test's first docstring line is what `make exercise` shows."""

import pytest

from lantern import case

BADGES = case.read("badge-log.csv")
CAMERA = case.read("gate-camera-log.csv")
MALHOTRA = dict(holder="R. Malhotra", left_door="ADMIN-MAIN", arrived_door="GATE-2-PED",
                camera="CAM-GATE-2", walk_minutes=5)

HEADER = "time,badge_id,holder,door,direction,result\n"
CAM_HEADER = "time,camera,event,detail\n"


def test_malhotra_times_come_from_the_badge_log(impl):
    """Malhotra's alibi uses his ADMIN-MAIN swipe out and his first GATE-2-PED swipe."""
    out = impl.check_alibi(BADGES, CAMERA, **MALHOTRA)
    assert out["left"] == "23:31:02", f"left should be his ADMIN-MAIN 'out' swipe, got {out}"
    assert out["arrived"] == "23:47:09", (
        "arrived should be the first GATE-2-PED swipe after he left, not the 23:58:30 swipe back in"
    )


def test_malhotra_gap_is_eleven_minutes_and_the_alibi_fails(impl):
    """16.1 minutes elapsed for a 5 minute walk: 11.1 unaccounted, so the alibi does not hold."""
    out = impl.check_alibi(BADGES, CAMERA, **MALHOTRA)
    assert out["elapsed_minutes"] == 16.1, f"23:31:02 to 23:47:09 is 16.1 minutes, got {out}"
    assert out["gap_minutes"] == 11.1, "gap is elapsed minus the walking time, to one decimal"
    assert out["holds"] is False, "an 11 minute gap is far beyond a 2 minute tolerance"


def test_the_gate_camera_corroborates_the_gate_swipe(impl):
    """The grey saloon on CAM-GATE-2 at 23:47:20 corroborates the 23:47:09 swipe."""
    out = impl.check_alibi(BADGES, CAMERA, **MALHOTRA)
    assert out["camera_seen"] == "23:47:20", f"first CAM-GATE-2 event after 23:47:09: {out}"
    assert out["corroborated"] is True


def test_a_walk_that_fits_holds(impl):
    """Someone who badges through in 5 min 30 s for a 5 minute walk has an alibi that holds."""
    badges = HEADER + ("22:00:00,B-1,A. Person,ADMIN-MAIN,out,granted\n"
                       "22:05:30,B-1,A. Person,GATE-2-PED,out,granted\n")
    cam = CAM_HEADER + "22:05:40,CAM-GATE-2,vehicle,car exits\n"
    out = impl.check_alibi(badges, cam, holder="A. Person", left_door="ADMIN-MAIN",
                           arrived_door="GATE-2-PED", camera="CAM-GATE-2", walk_minutes=5)
    assert out["elapsed_minutes"] == 5.5 and out["gap_minutes"] == 0.5, out
    assert out["holds"] is True, "a half-minute gap is inside the 2 minute tolerance"


def test_only_the_holders_rows_count(impl):
    """Another person's swipe at the same door is never taken as the holder's."""
    badges = HEADER + ("22:00:00,B-1,A. Person,ADMIN-MAIN,out,granted\n"
                       "22:01:00,B-2,B. Other,GATE-2-PED,out,granted\n"
                       "22:20:00,B-1,A. Person,GATE-2-PED,out,granted\n")
    out = impl.check_alibi(badges, CAM_HEADER, holder="A. Person", left_door="ADMIN-MAIN",
                           arrived_door="GATE-2-PED", camera="CAM-GATE-2", walk_minutes=5)
    assert out["arrived"] == "22:20:00", f"B. Other's 22:01:00 swipe is not A. Person's: {out}"
    assert out["gap_minutes"] == 15.0 and out["holds"] is False


def test_a_late_camera_event_is_not_corroboration(impl):
    """A camera event outside the window after the swipe does not corroborate it."""
    badges = HEADER + ("22:00:00,B-1,A. Person,ADMIN-MAIN,out,granted\n"
                       "22:05:00,B-1,A. Person,GATE-2-PED,out,granted\n")
    cam = CAM_HEADER + ("22:04:00,CAM-GATE-2,vehicle,before the swipe\n"
                        "22:15:00,CAM-GATE-2,vehicle,ten minutes later\n")
    out = impl.check_alibi(badges, cam, holder="A. Person", left_door="ADMIN-MAIN",
                           arrived_door="GATE-2-PED", camera="CAM-GATE-2", walk_minutes=5)
    assert out["camera_seen"] is None and out["corroborated"] is False, (
        f"only an event 0 to 120 seconds after the swipe counts, got {out}"
    )


def test_a_missing_swipe_is_an_error_not_a_guess(impl):
    """No swipe at the destination raises ValueError instead of inventing a time."""
    badges = HEADER + "22:00:00,B-1,A. Person,ADMIN-MAIN,out,granted\n"
    with pytest.raises(ValueError):
        impl.check_alibi(badges, CAM_HEADER, holder="A. Person", left_door="ADMIN-MAIN",
                         arrived_door="GATE-2-PED", camera="CAM-GATE-2", walk_minutes=5)
