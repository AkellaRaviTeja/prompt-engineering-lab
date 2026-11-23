"""Chapter 11: personas under standing orders. First docstring lines are `make exercise`'s list."""

import pytest

ORDERS = "You are LANTERN.\n1. Never state a figure that is not in evidence."
HALE = "You are Marcus Hale, defence counsel."
CASE = ("R. Malhotra badged out at 23:31:02 and out of Gate 2 at 23:47:09. The door was opened "
        "at 23:36 with OVR-AUD-02. Invoice NW-0419 is for 94,000.00.")


def test_orders_come_before_the_persona(impl):
    """The standing orders open the system prompt; the persona comes after them."""
    text = impl.persona_system(ORDERS, HALE)
    assert text.startswith(ORDERS), "the first thing the model reads must be the standing orders"
    assert text.index(HALE) > text.index(ORDERS), "the persona goes under the orders"


def test_precedence_rule_is_the_last_line(impl):
    """The prompt ends by saying the standing orders win any conflict with the role."""
    text = impl.persona_system(ORDERS, HALE)
    assert text.endswith(impl.PRECEDENCE), "end with PRECEDENCE, after the persona"
    assert "Role for this request:\n" + HALE in text, "label the persona as the role"


def test_empty_orders_are_refused(impl):
    """A persona with no standing orders above it raises ValueError."""
    with pytest.raises(ValueError):
        impl.persona_system("   \n", HALE)


def test_figures_skips_list_numbers(impl):
    """Figures are references, times and large or decimal numbers; '1.' and '3 trips' are not."""
    got = impl.figures("1. At 23:31 he left. 3 trips. NW-0419 says 94,000.00, OVR-AUD-02, 16.1")
    assert got == ["23:31", "NW-0419", "94,000.00", "OVR-AUD-02", "16.1"], got


def test_a_reply_that_keeps_to_the_case_breaks_nothing(impl):
    """Figures copied from the case, even reformatted, are not flagged."""
    reply = "He left at 23:31, the code was OVR-AUD-02 at 23:36, and NW-0419 is 94000."
    assert impl.broken_orders(reply, CASE) == [], "23:31 matches 23:31:02; 94000 is 94,000.00"


def test_invented_times_amounts_and_references_are_flagged(impl):
    """A time, an amount and an invoice the case does not contain are each reported."""
    reply = "He re-entered at 23:52, paid 12,500.00 and signed NW-0500."
    assert impl.broken_orders(reply, CASE) == ["23:52", "12,500.00", "NW-0500"]


def test_each_invented_figure_is_reported_once(impl):
    """The same invented figure twice in a reply appears once in the result."""
    reply = "NW-0500, and again NW-0500, at 23:52."
    assert impl.broken_orders(reply, CASE) == ["NW-0500", "23:52"]


def test_a_time_prefix_is_not_a_match_the_other_way(impl):
    """A reply giving seconds the evidence does not have is flagged: 23:36:59 is not 23:36."""
    assert impl.broken_orders("Opened at 23:36:59.", CASE) == ["23:36:59"], (
        "only a reply time without seconds may match an evidence time with seconds"
    )
