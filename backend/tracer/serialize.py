"""Turns live Python objects into the JSON-friendly snapshot format.

Every mutable or container object gets a stable identifier (``o1``, ``o2`` …)
the first time it is seen. The encoder keeps a strong reference to each
labelled object so that CPython cannot recycle its ``id()`` for a different
object later in the run, which would otherwise make two unrelated objects
share a label.

The encoder never calls user-defined code: it does not use ``repr()`` on
arbitrary objects and reads instance attributes through ``object.__getattribute__``.
"""

from __future__ import annotations

import types
from collections import deque
from typing import Any

PRIMITIVE_TYPES = (int, float, str, bool, type(None), complex)
SEQUENCE_TYPES = (list, tuple)
SET_TYPES = (set, frozenset)

MAX_REPR_CHARS = 200


def short_repr(value: Any, limit: int = MAX_REPR_CHARS) -> str:
    """repr() for builtin primitive values, robust to huge ints and long strings."""
    if type(value) is str and len(value) > limit:
        value = value[:limit]
        text = repr(value)
        return text[:-1] + "…" + text[-1]
    try:
        text = repr(value)
    except ValueError:  # int too large to convert to str
        return f"<int with {value.bit_length()} bits>"
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def is_primitive(value: Any) -> bool:
    return type(value) in PRIMITIVE_TYPES or type(value) is range


def encode_primitive(value: Any) -> dict:
    return {"kind": "prim", "type": type(value).__name__, "repr": short_repr(value)}


def _function_params(fn: types.FunctionType) -> list[str]:
    code = fn.__code__
    count = code.co_argcount + code.co_kwonlyargcount
    names = list(code.co_varnames[:count])
    flags = code.co_flags
    extra = count
    if flags & 0x04:  # CO_VARARGS
        names.insert(code.co_argcount, "*" + code.co_varnames[extra])
        extra += 1
    if flags & 0x08:  # CO_VARKEYWORDS
        names.append("**" + code.co_varnames[extra])
    return names


def _instance_attrs(obj: Any) -> dict | None:
    try:
        attrs = object.__getattribute__(obj, "__dict__")
    except Exception:
        return None
    return attrs if type(attrs) is dict else None


class HeapEncoder:
    def __init__(self, max_objects: int = 200, max_items: int = 100):
        self.max_objects = max_objects
        self.max_items = max_items
        self._labels: dict[int, str] = {}
        self._keepalive: list[Any] = []

    # -- identity -------------------------------------------------------
    def label(self, obj: Any) -> str:
        key = id(obj)
        label = self._labels.get(key)
        if label is None:
            label = f"o{len(self._labels) + 1}"
            self._labels[key] = label
            self._keepalive.append(obj)
        return label

    def has_label(self, obj: Any) -> bool:
        return id(obj) in self._labels

    # -- values ---------------------------------------------------------
    def encode_value(self, value: Any, queue: deque | None = None) -> dict:
        if is_primitive(value):
            return encode_primitive(value)
        label = self.label(value)
        if queue is not None:
            queue.append(value)
        return {"kind": "ref", "id": label}

    def snapshot(self, frames: list[tuple[str, str, int | None, dict, bool, Any]]) -> tuple[list[dict], dict]:
        """frames: (frame_id, name, line, variables, is_global, return_value or _NO_VALUE)."""
        queue: deque = deque()
        stack = []
        for depth, (frame_id, name, line, variables, is_global, ret) in enumerate(frames):
            local_list = []
            for var_name, value in list(variables.items()):
                if not visible_name(var_name):
                    continue
                local_list.append({"name": var_name, "value": self.encode_value(value, queue)})
            entry = {
                "id": frame_id,
                "name": name,
                "line": line,
                "isGlobal": is_global,
                "depth": depth,
                "locals": local_list,
                "returnValue": None if ret is NO_VALUE else self.encode_value(ret, queue),
            }
            stack.append(entry)

        # Objects past max_objects are left out; the frontend renders a
        # reference to a missing id as "not shown".
        heap: dict[str, dict] = {}
        while queue and len(heap) < self.max_objects:
            obj = queue.popleft()
            label = self.label(obj)
            if label not in heap:
                heap[label] = self._encode_object(obj, label, queue)
        return stack, heap

    def _encode_object(self, obj: Any, label: str, queue: deque) -> dict:
        kind = type(obj)
        if kind in SEQUENCE_TYPES or kind in SET_TYPES:
            items_src = list(obj)
            if kind in SET_TYPES:
                # Show sets in a stable order (sets themselves are unordered).
                items_src.sort(key=lambda v: (type(v).__name__, short_repr(v) if is_primitive(v) else self.label(v)))
            shown = items_src[: self.max_items]
            return {
                "id": label,
                "type": kind.__name__,
                "items": [self.encode_value(v, queue) for v in shown],
                "length": len(items_src),
                "truncated": len(items_src) > len(shown),
            }
        if kind is dict:
            pairs = list(obj.items())
            shown = pairs[: self.max_items]
            return {
                "id": label,
                "type": "dict",
                "entries": [
                    {"key": self.encode_value(k, queue), "value": self.encode_value(v, queue)} for k, v in shown
                ],
                "length": len(pairs),
                "truncated": len(pairs) > len(shown),
            }
        if kind is types.FunctionType:
            name = obj.__name__
            return {
                "id": label,
                "type": "function",
                "name": "lambda" if name == "<lambda>" else name,
                "params": _function_params(obj),
                "line": obj.__code__.co_firstlineno,
            }
        if kind is types.MethodType:
            return {
                "id": label,
                "type": "other",
                "typeName": "method",
                "repr": f"bound method {obj.__func__.__name__}",
            }
        if kind is types.ModuleType:
            return {"id": label, "type": "other", "typeName": "module", "repr": f"module {obj.__name__}"}
        if isinstance(obj, type):
            members = [n for n in vars(obj) if not n.startswith("__")]
            return {"id": label, "type": "class", "name": obj.__name__, "members": members}
        if isinstance(obj, (types.BuiltinFunctionType, types.BuiltinMethodType)):
            return {"id": label, "type": "other", "typeName": "builtin function", "repr": f"built-in {obj.__name__}"}

        attrs = _instance_attrs(obj)
        type_name = type(obj).__name__
        if attrs is not None and type(obj).__module__ == "__main__":
            pairs = [(k, v) for k, v in attrs.items() if type(k) is str]
            shown = pairs[: self.max_items]
            return {
                "id": label,
                "type": "instance",
                "className": type_name,
                "entries": [
                    {"key": encode_primitive(k), "value": self.encode_value(v, queue)} for k, v in shown
                ],
                "length": len(pairs),
                "truncated": len(pairs) > len(shown),
            }
        return {"id": label, "type": "other", "typeName": type_name, "repr": f"{type_name} object"}


class _NoValue:
    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "NO_VALUE"


NO_VALUE = _NoValue()


def visible_name(name: str) -> bool:
    if name.startswith("__") and name.endswith("__"):
        return False
    return not (name.startswith(".") or name.startswith("<"))
