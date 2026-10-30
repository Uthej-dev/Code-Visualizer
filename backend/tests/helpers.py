"""Helpers for reading trace snapshots in tests."""


def frame(step, name="Global frame"):
    return next(f for f in step["stack"] if f["name"] == name)


def var(step, name, frame_name="Global frame"):
    """Decoded value of a variable in a step: Python value for primitives,
    or ('ref', id) for objects."""
    for v in frame(step, frame_name)["locals"]:
        if v["name"] == name:
            return decode(step, v["value"])
    raise KeyError(name)


def has_var(step, name, frame_name="Global frame"):
    try:
        f = frame(step, frame_name)
    except StopIteration:
        return False
    return any(v["name"] == name for v in f["locals"])


def ref_id(step, name, frame_name="Global frame"):
    for v in frame(step, frame_name)["locals"]:
        if v["name"] == name:
            assert v["value"]["kind"] == "ref"
            return v["value"]["id"]
    raise KeyError(name)


def decode(step, value):
    """Turn an encoded Value into a plain Python structure (for assertions)."""
    import ast

    if value["kind"] == "prim":
        return ast.literal_eval(value["repr"]) if value["type"] != "range" else value["repr"]
    obj = step["heap"][value["id"]]
    t = obj["type"]
    if t == "list":
        return [decode(step, v) for v in obj["items"]]
    if t == "tuple":
        return tuple(decode(step, v) for v in obj["items"])
    if t in ("set", "frozenset"):
        return {decode(step, v) for v in obj["items"]}
    if t == "dict":
        return {decode(step, e["key"]): decode(step, e["value"]) for e in obj["entries"]}
    return ("obj", t, value["id"])


def output_at(trace, step):
    return trace["output"][: step["outputLength"]]


def steps_on_line(trace, line, event="line"):
    return [s for s in trace["steps"] if s["line"] == line and s["event"] == event]
