"""Run every shared sample through the real sandbox (child process) and check
the resulting trace against expected program states."""

import pytest

from app.models import TraceResponse
from app.samples import load_samples
from app.sandbox import run_code
from helpers import output_at, ref_id, steps_on_line, var

SAMPLES = {s["id"]: s for s in load_samples()}


@pytest.fixture(scope="module")
def traces():
    return {sid: run_code(s["code"]) for sid, s in SAMPLES.items()}


def test_all_samples_produce_valid_traces(traces):
    assert len(traces) == 10
    for sid, trace in traces.items():
        TraceResponse.model_validate(trace)
        assert len(trace["steps"]) >= 5, sid
        changed = sum(1 for s in trace["steps"] if s["changes"] or s["heapChanges"])
        assert changed >= 3, f"{sid} should show meaningful changes"


def test_variables_sample(traces):
    t = traces["variables"]
    final = t["steps"][-1]
    assert var(final, "age") == 37 and var(final, "greeting") == "Hello, Ada"
    assert t["output"] == "Hello, Ada\nNext year Ada will be 38\n"


def test_add_sample(traces):
    t = traces["add"]
    c_step = steps_on_line(t, 4)[0]
    assert var(c_step, "c") == 42
    assert "Compute 12 + 30 → 42" in c_step["explanation"]


def test_largest_sample_takes_elif_branch(traces):
    t = traces["largest"]
    lines = [s["line"] for s in t["steps"] if s["event"] == "line"]
    assert 9 in lines and 7 not in lines and 11 not in lines
    assert var(t["steps"][-1], "largest") == 42


def test_loop_sample_running_total(traces):
    t = traces["loop"]
    totals = [var(s, "total") for s in steps_on_line(t, 5)]
    assert totals == [4, 12, 27, 43]
    assert output_at(t, steps_on_line(t, 6)[1]) == "Added 4 -> total is 4\nAdded 8 -> total is 12\n"


def test_search_sample_breaks_at_match(traces):
    t = traces["search"]
    assert var(t["steps"][-1], "found_at") == 2
    assert len([s for s in steps_on_line(t, 7) if not s["loop"]["ended"]]) == 3
    assert t["output"] == "Priya found at index 2\n"


def test_modify_list_sample_aliasing(traces):
    t = traces["modify-list"]
    after_remove = steps_on_line(t, 8)[0]
    assert ref_id(after_remove, "scores") == ref_id(after_remove, "backup")
    assert ref_id(after_remove, "copy") != ref_id(after_remove, "scores")
    assert var(after_remove, "backup") == [75, 90, 100]
    rebind = steps_on_line(t, 14)[0]
    assert ref_id(rebind, "scores") != ref_id(rebind, "backup")
    assert next(c for c in rebind["changes"] if c["name"] == "scores")["kind"] == "rebound"


def test_function_sample_stack(traces):
    t = traces["function"]
    names = {tuple(f["name"] for f in s["stack"]) for s in t["steps"]}
    assert ("Global frame", "describe", "area") in names
    assert var(t["steps"][-1], "room") == 12


def test_factorial_sample(traces):
    t = traces["factorial"]
    assert max(len(s["stack"]) for s in t["steps"]) == 5
    assert var(t["steps"][-1], "answer") == 24
    assert t["output"] == "4! = 24\n"


def test_dictionary_sample(traces):
    t = traces["dictionary"]
    assert var(steps_on_line(t, 5)[0], "stock") == {"apples": 3, "bananas": 7}
    assert var(t["steps"][-1], "total") == 10


def test_error_sample(traces):
    t = traces["error"]
    assert t["status"] == "error"
    assert t["error"]["type"] == "IndexError" and t["error"]["line"] == 5
    last = t["steps"][-1]
    assert last["event"] == "exception" and var(last, "i") == 3
    assert t["output"].count("Reading") == 3
