"""Pydantic models for the API. Mirrors ``frontend/src/types/trace.ts``."""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrimitiveValue(_Model):
    kind: Literal["prim"]
    type: str
    repr: str


class RefValue(_Model):
    kind: Literal["ref"]
    id: str


Value = Annotated[Union[PrimitiveValue, RefValue], Field(discriminator="kind")]


class DictEntry(_Model):
    key: Value
    value: Value


class HeapObject(_Model):
    id: str
    type: Literal["list", "tuple", "set", "frozenset", "dict", "instance", "function", "class", "other"]
    items: Optional[list[Value]] = None
    entries: Optional[list[DictEntry]] = None
    length: Optional[int] = None
    truncated: Optional[bool] = None
    name: Optional[str] = None
    params: Optional[list[str]] = None
    line: Optional[int] = None
    className: Optional[str] = None
    members: Optional[list[str]] = None
    typeName: Optional[str] = None
    repr: Optional[str] = None


class Variable(_Model):
    name: str
    value: Value


class Frame(_Model):
    id: str
    name: str
    line: Optional[int]
    isGlobal: bool
    depth: int
    locals: list[Variable]
    returnValue: Optional[Value] = None


class VariableChange(_Model):
    frameId: str
    name: str
    kind: Literal["created", "rebound", "mutated", "removed"]
    before: Optional[Value] = None
    after: Optional[Value] = None


class HeapChange(_Model):
    id: str
    kind: Literal["created", "mutated"]
    changed: list[str]
    added: list[str]
    removed: list[str]


class ExceptionInfo(_Model):
    type: str
    message: str
    line: Optional[int]
    uncaught: bool


class ConditionInfo(_Model):
    result: bool


class LoopInfo(_Model):
    line: int
    iteration: int
    ended: bool


class Step(_Model):
    index: int
    eventId: str
    event: Literal["line", "call", "return", "exception", "finish"]
    line: Optional[int]
    endLine: Optional[int]
    frameId: str
    funcName: str
    stack: list[Frame]
    heap: dict[str, HeapObject]
    outputLength: int
    changes: list[VariableChange]
    heapChanges: list[HeapChange]
    summary: str
    explanation: list[str]
    exception: Optional[ExceptionInfo] = None
    condition: Optional[ConditionInfo] = None
    loop: Optional[LoopInfo] = None


class TraceError(_Model):
    phase: Literal["input", "syntax", "unsupported", "runtime", "limit", "internal"]
    type: str
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    hint: Optional[str] = None


class TraceStats(BaseModel):
    stepCount: int
    durationMs: float
    isolation: Optional[list[str]] = None


class TraceResponse(_Model):
    version: int
    status: Literal["ok", "error", "limit", "internal"]
    steps: list[Step]
    output: str
    error: Optional[TraceError] = None
    truncated: bool
    limitReason: Optional[str] = None
    limits: dict[str, int]
    stats: TraceStats


class TraceRequest(_Model):
    code: str = Field(max_length=20_000)


class Sample(_Model):
    id: str
    title: str
    description: str
    concepts: list[str]
    code: str
