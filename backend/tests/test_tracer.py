"""Unit tests for the tracing engine (run in-process with trusted code)."""

import pytest

from helpers import decode, has_var, output_at, ref_id, steps_on_line, var
from tracer import TraceLimits, trace_code


def run(code, **limits):
    return trace_code(code, TraceLimits(**limits) if limits else None)


# --- variables ---------------------------------------------------------------

def test_variable_creation_and_modification():
    t = run("a = 1\nb = a + 2\na = 10\n")
    assert t["status"] == "ok"
    s0, s1, s2, fin = t["steps"]
    assert s0["line"] == 1 and var(s0, "a") == 1
    assert not has_var(s0, "b"), "variables must not appear before they exist"
    assert var(s1, "b") == 3
    assert {(c["name"], c["kind"]) for c in s1["changes"]} == {("b", "created")}
    assert var(s2, "a") == 10
    change = s2["changes"][0]
    assert change["kind"] == "rebound" and change["before"]["repr"] == "1" and change["after"]["repr"] == "10"
    assert fin["event"] == "finish"


def test_value_types():
    t = run("i = 3\nf = 2.5\ns = 'hi'\nb = True\nn = None\nt = (1, 2)\nst = {3}\n")
    last = t["steps"][-1]
    types = {v["name"]: v["value"].get("type") for v in last["stack"][0]["locals"]}
    assert types["i"] == "int" and types["f"] == "float" and types["s"] == "str"
    assert types["b"] == "bool" and types["n"] == "NoneType"
    assert var(last, "t") == (1, 2) and var(last, "st") == {3}


def test_explanation_shows_actual_values():
    t = run("a = 3\nb = 4\nc = a + b\n")
    text = t["steps"][2]["explanation"]
    assert "Read a → 3" in text and "Read b → 4" in text
    assert "Compute 3 + 4 → 7" in text
    assert any("store 7" in line for line in text)


# --- control flow ------------------------------------------------------------

def test_for_loop_iteration_count():
    t = run("total = 0\nfor x in [5, 6, 7]:\n    total += x\n")
    headers = steps_on_line(t, 2)
    assert [s["loop"]["iteration"] for s in headers] == [1, 2, 3, 3]
    assert [s["loop"]["ended"] for s in headers] == [False, False, False, True]
    assert [var(s, "x") for s in headers[:3]] == [5, 6, 7]
    assert len(steps_on_line(t, 3)) == 3
    assert var(t["steps"][-1], "total") == 18


def test_while_loop_iteration_count_and_condition():
    t = run("i = 0\nwhile i < 3:\n    i = i + 1\n")
    headers = steps_on_line(t, 2)
    assert [s["condition"]["result"] for s in headers] == [True, True, True, False]
    assert headers[-1]["loop"] == {"line": 2, "iteration": 3, "ended": True}


def test_nested_loops_reset_inner_counter():
    t = run("for a in range(2):\n    for b in range(3):\n        pass\n")
    inner = [s["loop"] for s in steps_on_line(t, 2)]
    assert [l["iteration"] for l in inner if not l["ended"]] == [1, 2, 3, 1, 2, 3]


def test_empty_loop_never_runs_body():
    t = run("for x in []:\n    y = 1\nz = 2\n")
    assert steps_on_line(t, 2) == []
    assert steps_on_line(t, 1)[0]["loop"]["ended"] is True


@pytest.mark.parametrize("x,branch_line", [(1, 3), (5, 5), (9, 7)])
def test_if_elif_else_branches(x, branch_line):
    code = f"x = {x}\nif x < 3:\n    r = 'low'\nelif x < 7:\n    r = 'mid'\nelse:\n    r = 'high'\n"
    t = run(code)
    executed = [s["line"] for s in t["steps"] if s["event"] == "line"]
    assert branch_line in executed
    assert {3, 5, 7} - {branch_line} & set(executed) == set()
    first_if = steps_on_line(t, 2)[0]
    assert first_if["condition"]["result"] is (x < 3)


# --- functions ---------------------------------------------------------------

def test_function_call_and_return():
    t = run("def add(a, b):\n    s = a + b\n    return s\nr = add(2, 3)\n")
    events = [(s["event"], s["line"]) for s in t["steps"]]
    assert events == [("line", 1), ("call", 1), ("line", 2), ("return", 3), ("line", 4), ("finish", None)]
    call = t["steps"][1]
    assert [f["name"] for f in call["stack"]] == ["Global frame", "add"]
    assert var(call, "a", "add") == 2 and var(call, "b", "add") == 3
    assert not has_var(call, "s", "add")
    ret = t["steps"][3]
    assert decode(ret, ret["stack"][1]["returnValue"]) == 5
    after = t["steps"][4]
    assert len(after["stack"]) == 1 and var(after, "r") == 5


def test_function_without_return_returns_none():
    t = run("def hello():\n    x = 1\nhello()\n")
    ret = next(s for s in t["steps"] if s["event"] == "return")
    assert ret["stack"][-1]["returnValue"]["repr"] == "None"


def test_nested_calls():
    t = run("def sq(n):\n    return n * n\ndef f(a):\n    return sq(a) + 1\nv = f(3)\n")
    max_depth = max(len(s["stack"]) for s in t["steps"])
    assert max_depth == 3
    assert var(t["steps"][-1], "v") == 10


def test_recursive_calls_have_separate_frames():
    t = run("def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)\nr = fact(4)\n")
    deepest = max(t["steps"], key=lambda s: len(s["stack"]))
    names = [f["name"] for f in deepest["stack"]]
    assert names == ["Global frame", "fact", "fact", "fact", "fact"]
    ns = [decode(deepest, f["locals"][0]["value"]) for f in deepest["stack"][1:]]
    assert ns == [4, 3, 2, 1]
    returns = [decode(s, s["stack"][-1]["returnValue"]) for s in t["steps"] if s["event"] == "return"]
    assert returns == [1, 2, 6, 24]
    assert len({s["frameId"] for s in t["steps"] if s["event"] == "call"}) == 4
    assert var(t["steps"][-1], "r") == 24


# --- collections & references ---------------------------------------------------

def test_list_mutation_is_not_rebinding():
    t = run("lst = [1, 2]\nlst.append(3)\nlst[0] = 9\n")
    s0, s1, s2 = t["steps"][:3]
    oid = ref_id(s0, "lst")
    assert ref_id(s1, "lst") == oid == ref_id(s2, "lst")
    assert s1["changes"] == [{"frameId": "global", "name": "lst", "kind": "mutated", "before": {"kind": "ref", "id": oid}, "after": {"kind": "ref", "id": oid}}]
    assert s1["heapChanges"][0]["added"] == ["2"]
    assert s2["heapChanges"][0]["changed"] == ["0"]
    assert var(s2, "lst") == [9, 2, 3]


def test_rebinding_gets_new_object():
    t = run("lst = [1]\nlst = [1]\n")
    a, b = t["steps"][:2]
    assert ref_id(a, "lst") != ref_id(b, "lst")
    assert b["changes"][0]["kind"] == "rebound"


def test_shared_references_point_to_same_object():
    t = run("a = [1, 2]\nb = a\nc = list(a)\nb.append(3)\n")
    s = t["steps"][3]
    assert ref_id(s, "a") == ref_id(s, "b")
    assert ref_id(s, "c") != ref_id(s, "a")
    assert var(s, "a") == [1, 2, 3] and var(s, "c") == [1, 2]
    kinds = {c["name"]: c["kind"] for c in s["changes"]}
    assert kinds == {"a": "mutated", "b": "mutated"}


def test_nested_collections_and_identity_across_steps():
    t = run("inner = [1]\nouter = [inner, inner]\ninner.append(2)\nd = {'k': outer}\n")
    last = t["steps"][3]
    outer_obj = last["heap"][ref_id(last, "outer")]
    assert outer_obj["items"][0] == outer_obj["items"][1] == {"kind": "ref", "id": ref_id(last, "inner")}
    assert var(last, "d") == {"k": [[1, 2], [1, 2]]}


def test_dictionary_updates():
    t = run("d = {'a': 1}\nd['b'] = 2\nd['a'] = 5\ndel d['b']\n")
    s1, s2, s3 = t["steps"][1:4]
    assert s1["heapChanges"][0]["added"] == ["str:'b'"]
    assert s2["heapChanges"][0]["changed"] == ["str:'a'"]
    assert s3["heapChanges"][0]["removed"] == ["str:'b'"]
    assert var(s3, "d") == {"a": 5}


def test_mutation_inside_function_visible_to_caller():
    t = run("def push(xs):\n    xs.append(0)\nnums = []\npush(nums)\n")
    in_func = next(s for s in t["steps"] if s["event"] == "line" and s["line"] == 2)
    assert ref_id(in_func, "xs", "push") == ref_id(in_func, "nums")
    assert var(t["steps"][-1], "nums") == [0]


# --- output --------------------------------------------------------------------

def test_output_accumulates_per_step():
    t = run("print('a')\nx = 1\nprint('b', x)\n")
    outs = [output_at(t, s) for s in t["steps"]]
    assert outs == ["a\n", "a\n", "a\nb 1\n", "a\nb 1\n"]


# --- exceptions ----------------------------------------------------------------

def test_uncaught_exception():
    t = run("x = 1\ny = x / 0\nz = 3\n")
    assert t["status"] == "error"
    assert t["error"]["type"] == "ZeroDivisionError" and t["error"]["line"] == 2
    last = t["steps"][-1]
    assert last["event"] == "exception" and last["exception"]["uncaught"] is True
    assert not has_var(last, "y")


def test_exception_in_function_reported_at_origin():
    t = run("def f(xs):\n    return xs[5]\nf([1])\n")
    exc_steps = [s for s in t["steps"] if s["event"] == "exception"]
    assert len(exc_steps) == 1 and exc_steps[0]["line"] == 2
    assert [f["name"] for f in exc_steps[0]["stack"]] == ["Global frame", "f"]
    assert t["error"]["type"] == "IndexError"


def test_caught_exception_continues():
    t = run("try:\n    v = int('x')\nexcept ValueError:\n    v = -1\nprint(v)\n")
    assert t["status"] == "ok"
    exc = next(s for s in t["steps"] if s["event"] == "exception")
    assert exc["exception"]["uncaught"] is False
    assert var(t["steps"][-1], "v") == -1
    assert t["output"] == "-1\n"


def test_name_error():
    t = run("print(undefined_name)\n")
    assert t["error"]["type"] == "NameError" and t["error"]["hint"]


# --- validation and limits -----------------------------------------------------

def test_syntax_error_reports_line():
    t = run("x = 1\nif x\n    pass\n")
    assert t["status"] == "error" and t["error"]["phase"] == "syntax" and t["error"]["line"] == 2
    assert t["steps"] == []


@pytest.mark.parametrize("code", [
    "import os\n",
    "x = ().__class__\n",
    "open('f')\n",
    "eval('1')\n",
    "def g():\n    yield 1\n",
    "with x:\n    pass\n",
    "y = input()\n",
])
def test_unsupported_code_is_rejected(code):
    t = run(code)
    assert t["status"] == "error" and t["error"]["phase"] == "unsupported"
    assert t["error"]["line"] is not None


def test_step_limit_stops_infinite_loop():
    t = run("while True:\n    pass\n", max_steps=50)
    assert t["status"] == "limit" and t["truncated"] is True
    assert len(t["steps"]) == 50


def test_output_limit():
    t = run("for i in range(100):\n    print('x' * 50)\n", max_output_chars=200)
    assert t["status"] == "limit" and len(t["output"]) == 200


def test_recursion_depth_limit():
    t = run("def f(n):\n    return f(n + 1)\nf(0)\n", max_stack_depth=20)
    assert t["status"] == "limit" and t["error"]["type"] == "RecursionError"


# --- snapshot consistency --------------------------------------------------------

def _all_refs(value_holder):
    if isinstance(value_holder, dict):
        if value_holder.get("kind") == "ref":
            yield value_holder["id"]
        for v in value_holder.values():
            yield from _all_refs(v)
    elif isinstance(value_holder, list):
        for v in value_holder:
            yield from _all_refs(v)


def test_snapshots_are_self_contained_and_ordered():
    code = open(__file__.replace("tests/test_tracer.py", "../shared/samples/08_recursion.py")).read()
    t = run(code)
    previous_output = 0
    for i, step in enumerate(t["steps"]):
        assert step["index"] == i and step["eventId"] == f"e{i + 1}"
        for ref in _all_refs(step["stack"]):
            assert ref in step["heap"], f"dangling reference {ref} at step {i}"
        for obj in step["heap"].values():
            for ref in _all_refs(obj):
                assert ref in step["heap"]
        assert step["outputLength"] >= previous_output
        previous_output = step["outputLength"]


def test_tracing_is_deterministic():
    code = "a = [1, 2]\nb = {'x': a}\nfor v in a:\n    b[v] = v * 2\n"
    t1, t2 = run(code), run(code)
    for t in (t1, t2):
        t["stats"].pop("durationMs")
    assert t1 == t2


# --- broader language coverage ---------------------------------------------------

def test_class_instance_attributes_and_mutation():
    t = run("class P:\n    def __init__(self, x):\n        self.x = x\np = P(3)\nq = p\nq.x = 9\n")
    assert t["status"] == "ok"
    assert sum(1 for s in t["steps"] if s["summary"] == "Define class P") == 1
    last = t["steps"][-2]
    obj = last["heap"][ref_id(last, "p")]
    assert obj["type"] == "instance" and obj["className"] == "P"
    assert ref_id(last, "p") == ref_id(last, "q")
    assert obj["entries"][0]["value"]["repr"] == "9"
    assert any(".x = 9" in b for b in last["explanation"])


def test_lambda_and_comprehension():
    t = run("sq = lambda v: v * v\nnums = [sq(i) for i in range(3)]\n")
    assert t["status"] == "ok"
    assert [s["funcName"] for s in t["steps"] if s["event"] == "call"] == ["lambda"] * 3
    assert var(t["steps"][-1], "nums") == [0, 1, 4]


def test_closure_and_nonlocal():
    t = run("def outer():\n    c = 0\n    def inner():\n        nonlocal c\n        c += 1\n        return c\n    inner()\n    return inner()\nr = outer()\n")
    assert t["status"] == "ok" and var(t["steps"][-1], "r") == 2


def test_cyclic_structures_do_not_hang():
    t = run("a = []\na.append(a)\n")
    s = t["steps"][1]
    oid = ref_id(s, "a")
    assert s["heap"][oid]["items"] == [{"kind": "ref", "id": oid}]
