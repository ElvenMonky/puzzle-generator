import random
from typing import TypedDict, Union
from z3 import And, If

RangeSpec = Union[int, list[int]]

class SizeSpec(TypedDict, total=False):
    width: RangeSpec
    height: RangeSpec
    min: RangeSpec
    max: RangeSpec
    top: RangeSpec
    bottom: RangeSpec
    left: RangeSpec
    right: RangeSpec
    ratio: RangeSpec
    area: RangeSpec

def parse_range(spec: RangeSpec) -> tuple[int, int, int]:
    if isinstance(spec, int):
        return int(spec), int(spec), 1
    l = len(spec)
    if l == 0:
        0, 0, 1
    return int(spec[0]), int(spec[1 if l > 1 else 0]), int(spec[2]) if l > 2 else 1

def roll_range(spec: RangeSpec, rng: random.Random = None) -> int:
    if isinstance(spec, int):
        return int(spec)
    lo, hi, step = parse_range(spec)
    n = (hi - lo) // step
    return lo + (rng or random).randint(0, n) * step

def range_expr(var, spec: RangeSpec):
    lo, hi, step = parse_range(spec)
    if step == 1:
        return And(var >= lo, var <= hi)
    return And(var >= lo, var <= hi, (var - lo) % step == 0)

def size_constraints(x, y, w, h, size: SizeSpec, pw, ph):
    c = []
    if "width" in size: c.append(range_expr(w, size["width"]))
    if "height" in size: c.append(range_expr(h, size["height"]))
    if "top" in size: c.append(range_expr(y, size["top"]))
    if "bottom" in size: c.append(range_expr(ph - 1 - (y + h - 1), size["bottom"]))
    if "left" in size: c.append(range_expr(x, size["left"]))
    if "right" in size: c.append(range_expr(pw - 1 - (x + w - 1), size["right"]))
    if "min" in size or "max" in size:
        lo, hi = size.get("min", [1, 1]), size.get("max", size.get("min", [1, 1]))
        c.append(If(w <= h, And(range_expr(w, lo), range_expr(h, hi)),
                     And(range_expr(h, lo), range_expr(w, hi))))
    if "ratio" in size:
        r_lo, r_hi, _ = parse_range(size["ratio"])
        longer, shorter = If(w > h, w, h), If(w > h, h, w)
        c.append(And(longer >= shorter * r_lo, longer <= shorter * r_hi))
    if "area" in size:
        a_lo, a_hi, _ = parse_range(size["area"])
        c.append(And(w * h >= a_lo, w * h <= a_hi))
    return c
