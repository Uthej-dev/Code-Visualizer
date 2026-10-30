"""Compares two consecutive snapshots.

The distinction the visualizer cares most about:

* **rebound** – a variable now points at a different value/object;
* **mutated** – a variable still points at the *same* object, but that
  object's contents changed (e.g. ``lst.append(4)``).
"""

from __future__ import annotations


def value_key(value: dict) -> str:
    """A hashable identity for a Value: primitives by repr, refs by object id."""
    if value["kind"] == "ref":
        return "@" + value["id"]
    return f"{value['type']}:{value['repr']}"


def _keyed_members(obj: dict) -> dict[str, dict] | None:
    t = obj["type"]
    if t in ("list", "tuple"):
        return {str(i): v for i, v in enumerate(obj["items"])}
    if t in ("set", "frozenset"):
        return {value_key(v): v for v in obj["items"]}
    if t in ("dict", "instance"):
        return {value_key(e["key"]): e["value"] for e in obj["entries"]}
    return None


def member_label(obj: dict, key: str) -> str:
    """Human-readable label for a member key produced by ``_keyed_members``."""
    if obj["type"] in ("list", "tuple"):
        return key
    if key.startswith("@"):
        return "<object>"
    label = key.split(":", 1)[1]
    if obj["type"] == "instance" and len(label) >= 2 and label[0] == label[-1] and label[0] in "'\"":
        return label[1:-1]  # attribute names are shown without quotes
    return label


def heap_object_change(old: dict, new: dict) -> dict | None:
    if old == new:
        return None
    old_members = _keyed_members(old)
    new_members = _keyed_members(new)
    if old_members is None or new_members is None:
        return {"id": new["id"], "kind": "mutated", "changed": [], "added": [], "removed": []}
    changed = [k for k, v in new_members.items() if k in old_members and old_members[k] != v]
    added = [k for k in new_members if k not in old_members]
    removed = [k for k in old_members if k not in new_members]
    if not (changed or added or removed):
        if old.get("length") == new.get("length"):
            return None
    return {"id": new["id"], "kind": "mutated", "changed": changed, "added": added, "removed": removed}


def diff_snapshots(prev_stack: list[dict], prev_heap: dict, stack: list[dict], heap: dict) -> tuple[list[dict], list[dict]]:
    heap_changes: list[dict] = []
    mutated_ids: set[str] = set()
    for oid, obj in heap.items():
        old = prev_heap.get(oid)
        if old is None:
            heap_changes.append({"id": oid, "kind": "created", "changed": [], "added": [], "removed": []})
            continue
        change = heap_object_change(old, obj)
        if change:
            heap_changes.append(change)
            mutated_ids.add(oid)

    prev_frames = {f["id"]: f for f in prev_stack}
    changes: list[dict] = []
    for frame in stack:
        old_frame = prev_frames.get(frame["id"])
        old_vars = {v["name"]: v["value"] for v in old_frame["locals"]} if old_frame else {}
        new_names = set()
        for var in frame["locals"]:
            name, value = var["name"], var["value"]
            new_names.add(name)
            before = old_vars.get(name)
            if before is None:
                kind = "created"
            elif before != value:
                kind = "rebound"
            elif value["kind"] == "ref" and value["id"] in mutated_ids:
                kind = "mutated"
            else:
                continue
            changes.append({"frameId": frame["id"], "name": name, "kind": kind, "before": before, "after": value})
        for name, before in old_vars.items():
            if name not in new_names:
                changes.append({"frameId": frame["id"], "name": name, "kind": "removed", "before": before, "after": None})
    return changes, heap_changes
