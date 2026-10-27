"""Evaluator for D2's skill formula language (Skills.txt / SkillDesc.txt "calc" columns).

Supports: numbers, + - * / %, comparisons, ?:, parentheses, min()/max(),
lvl, blvl, par1-8, ln12/ln34/ln56/ln78 (linear), dm12/dm34/dm56/dm78 (diminishing),
edmn/edmx/edns/ednx (elemental damage), dmmn/dmmx (physical), toht, mana, clc1-4,
skill('Name'.lvl / .blvl / .parN / .ln12 ...) and stat('name'.base/.accr) (stats -> 0).
Integer arithmetic like the game. Unknown names evaluate to 0.
"""
import re

_TOKEN = re.compile(r"\s*(?:(\d+)|('(?:[^']*)'\.[A-Za-z0-9]+)|([A-Za-z_][A-Za-z0-9_]*)|(<=|>=|==|!=|[-+*/%()?:<>,]))")


def _tokens(expr):
    expr = expr.strip().strip('"')
    pos, out = 0, []
    while pos < len(expr):
        m = _TOKEN.match(expr, pos)
        if not m:
            if expr[pos:].strip() == "":
                break
            raise ValueError("bad formula near %r" % expr[pos:pos + 10])
        num, ref, name, op = m.groups()
        if num is not None:
            out.append(("n", int(num)))
        elif ref is not None:
            q = ref.rindex("'")
            out.append(("ref", (ref[1:q], ref[q + 2:])))
        elif name is not None:
            out.append(("id", name))
        else:
            out.append(("op", op))
        pos = m.end()
    return out


def _idiv(a, b):
    if b == 0:
        return 0
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


class Parser:
    def __init__(self, toks, env):
        self.t = toks
        self.i = 0
        self.env = env

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self, op=None):
        tok = self.peek()
        if op is not None and tok != ("op", op):
            raise ValueError("expected %s" % op)
        self.i += 1
        return tok

    def parse(self):
        v = self.ternary()
        return v

    def ternary(self):
        c = self.compare()
        if self.peek() == ("op", "?"):
            self.take("?")
            a = self.ternary()
            self.take(":")
            b = self.ternary()
            return a if c else b
        return c

    def compare(self):
        a = self.additive()
        while self.peek()[0] == "op" and self.peek()[1] in ("<", ">", "<=", ">=", "==", "!="):
            op = self.take()[1]
            b = self.additive()
            a = int({"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b, "==": a == b, "!=": a != b}[op])
        return a

    def additive(self):
        a = self.term()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.take()[1]
            b = self.term()
            a = a + b if op == "+" else a - b
        return a

    def term(self):
        a = self.unary()
        while self.peek() in (("op", "*"), ("op", "/"), ("op", "%")):
            op = self.take()[1]
            b = self.unary()
            if op == "*":
                a = a * b
            elif op == "/":
                a = _idiv(a, b)
            else:
                a = a % b if b else 0
        return a

    def unary(self):
        if self.peek() == ("op", "-"):
            self.take()
            return -self.unary()
        if self.peek() == ("op", "+"):
            self.take()
            return self.unary()
        return self.atom()

    def atom(self):
        kind, val = self.take()
        if kind == "n":
            return val
        if kind == "op" and val == "(":
            v = self.ternary()
            self.take(")")
            return v
        if kind == "id":
            low = val.lower()
            if low in ("min", "max") and self.peek() == ("op", "("):
                self.take("(")
                a = self.ternary()
                self.take(",")
                b = self.ternary()
                self.take(")")
                return min(a, b) if low == "min" else max(a, b)
            if low in ("skill", "stat", "sklvl", "miss") and self.peek() == ("op", "("):
                self.take("(")
                tok = self.take()
                args = []
                while self.peek() != ("op", ")") and self.peek()[0] is not None:
                    args.append(self.take())
                self.take(")")
                if tok[0] == "ref":
                    name, field = tok[1]
                    return self.env.ref(low, name, field)
                return 0
            return self.env.name(low)
        if kind == "ref":
            name, field = val
            return self.env.ref("skill", name, field)
        raise ValueError("unexpected %r" % (val,))


def evaluate(expr, env):
    if expr is None:
        return 0
    expr = str(expr).strip()
    if not expr:
        return 0
    try:
        return Parser(_tokens(expr), env).parse()
    except Exception:
        return 0


def linear(a, b, lvl):
    return a + (lvl - 1) * b


def diminishing(a, b, lvl):
    """D2's 'dm' curve: from a towards b with diminishing returns."""
    return a + _idiv(110 * lvl * (b - a), 100 * (lvl + 6))
