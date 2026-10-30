"""Maps source lines to the AST statements that own them."""

from __future__ import annotations

import ast
from dataclasses import dataclass

COMPOUND = (ast.If, ast.For, ast.While, ast.FunctionDef, ast.ClassDef, ast.Try)
LOOPS = (ast.For, ast.While)


@dataclass(frozen=True)
class Block:
    start: int
    end: int

    def contains(self, line: int | None) -> bool:
        return line is not None and self.start <= line <= self.end


def block_of(stmts: list[ast.stmt]) -> Block | None:
    if not stmts:
        return None
    return Block(stmts[0].lineno, max(s.end_lineno or s.lineno for s in stmts))


def header_end(stmt: ast.stmt) -> int:
    """Last line of a statement's *header* (for compound statements) or of the
    whole statement (for simple statements)."""
    body = getattr(stmt, "body", None)
    if isinstance(stmt, COMPOUND) and body:
        return max(stmt.lineno, body[0].lineno - 1)
    return stmt.end_lineno or stmt.lineno


class StatementIndex:
    """Finds the innermost statement whose header covers a given line."""

    def __init__(self, tree: ast.Module):
        self._by_line: dict[int, ast.stmt] = {}
        self.parent: dict[ast.stmt, ast.stmt | None] = {}
        self._walk(tree.body, None)

    def _walk(self, stmts: list[ast.stmt], parent: ast.stmt | None) -> None:
        for stmt in stmts:
            self.parent[stmt] = parent
            for line in range(stmt.lineno, header_end(stmt) + 1):
                # Compound statements only claim their header lines, so ranges
                # never overlap except for one-line compounds (header wins).
                self._by_line.setdefault(line, stmt)
            for field in ("body", "orelse", "finalbody"):
                child = getattr(stmt, field, None)
                if isinstance(child, list) and child and isinstance(child[0], ast.stmt):
                    self._walk(child, stmt)
            for handler in getattr(stmt, "handlers", []) or []:
                self._walk(handler.body, stmt)

    def lookup(self, line: int) -> ast.stmt | None:
        return self._by_line.get(line)

    def enclosing_loop(self, stmt: ast.stmt | None) -> ast.stmt | None:
        cur = self.parent.get(stmt) if stmt is not None else None
        while cur is not None:
            if isinstance(cur, LOOPS):
                return cur
            if isinstance(cur, (ast.FunctionDef, ast.ClassDef)):
                return None
            cur = self.parent.get(cur)
        return None
