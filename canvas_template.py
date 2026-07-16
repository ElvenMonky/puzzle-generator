import random
from dataclasses import dataclass, field
from typing import Literal, NotRequired, TypedDict, Union

from z3 import ArithRef, And, Or, If, Implies, Int, Solver, unsat

from canvas_instance import CanvasSpec, GeometrySpec

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

class CutSpec(TypedDict, total=False):
    tl: RangeSpec
    tr: RangeSpec
    br: RangeSpec
    bl: RangeSpec

class OriginSpec(TypedDict, total=False):
    x: RangeSpec
    y: RangeSpec

LinkTypeSpec = Literal["Line", "Diaonal"]
TypeSpec = Literal["Geometry", "Line", "Diaonal", "Point", "Rectangle"]
StrategySpec = Literal["random", "flow", "tree"]

class LinkSpec(TypedDict, total=False):
    type: Union[LinkTypeSpec, list[LinkTypeSpec]]
    gap: RangeSpec
    color: RangeSpec
    above: bool

class ItemSpec(TypedDict, total=False):
    type: Union[TypeSpec, list[TypeSpec]]
    size: SizeSpec
    color: RangeSpec
    geometries: list["GroupSpec"]
    fill_color: RangeSpec
    vertice_color: RangeSpec
    cut: CutSpec
    dir: RangeSpec
    origin: OriginSpec
    weight: float
    singleton: bool

class GroupSpec(ItemSpec, total=False):
    count: RangeSpec
    gap: RangeSpec
    strategy: StrategySpec
    prefix: list[int]
    pattern: list[int]
    pool: list["ItemSpec"]
    margin: RangeSpec
    link: LinkSpec
    levels: RangeSpec
    rows: RangeSpec
    cols: RangeSpec

class CanvasTemplateSpec(TypedDict):
    width: RangeSpec
    height: RangeSpec
    background: NotRequired[RangeSpec]
    geometries: list[GroupSpec]

# ==========================================
# RANGE UTILITIES
# ==========================================
def parse_range(spec: RangeSpec) -> tuple[int, int, int]:
    if isinstance(spec, (int, float)):
        return int(spec), int(spec), 1
    if len(spec) == 2:
        return int(spec[0]), int(spec[1]), 1
    return int(spec[0]), int(spec[1]), int(spec[2])

def roll_range(spec: RangeSpec) -> int:
    if isinstance(spec, (int, float)):
        return int(spec)
    lo, hi, step = parse_range(spec)
    if step == 1:
        return random.randint(lo, hi)
    n = (hi - lo) // step
    return lo + random.randint(0, n) * step

def add_range_constraint(var: ArithRef, spec: RangeSpec, solver: Solver) -> None:
    lo, hi, step = parse_range(spec)
    solver.add(var >= lo, var <= hi)
    if step > 1:
        solver.add((var - lo) % step == 0)

def range_expr(var: ArithRef, spec: RangeSpec):
    lo, hi, step = parse_range(spec)
    if step == 1:
        return And(var >= lo, var <= hi)
    return And(var >= lo, var <= hi, (var - lo) % step == 0)

KIND_DCOL = {0: 1, 1: 1, 2: 0, 3: -1, 4: -1, 5: -1, 6: 0, 7: 1}
KIND_DROW = {0: 0, 1: 1, 2: 1, 3: 1, 4: 0, 5: -1, 6: -1, 7: -1}

def corner_points(ox: int, oy: int, w: int, h: int, cuts: CutSpec) -> list[list[int]]:
    tl, tr, br, bl = cuts["tl"], cuts["tr"], cuts["br"], cuts["bl"]
    raw = []
    raw.append([ox + tl, oy])
    raw.append([ox + w - 1 - tr, oy])
    if tr: raw.append([ox + w - 1, oy + tr])
    raw.append([ox + w - 1, oy + h - 1 - br])
    if br: raw.append([ox + w - 1 - br, oy + h - 1])
    raw.append([ox + bl, oy + h - 1])
    if bl: raw.append([ox, oy + h - 1 - bl])
    if tl: raw.append([ox, oy + tl])

    pts = []
    for p in raw:
        if not pts or p != pts[-1]:
            pts.append(p)
    if len(pts) > 1 and pts[-1] == pts[0]:
        pts.pop()
    return pts

# ==========================================
# ROTATION HELPERS
# ==========================================
def rot_x(dx, dy, d):
    return If(d==0, dx,
           If(d==1, -dy,
           If(d==2, -dx,
           If(d==3,  dy,
           If(d==4, -dx,
           If(d==5, -dy,
           If(d==6,  dx,
                     dy)))))))

def rot_y(dx, dy, d):
    return If(d==0, dy,
           If(d==1,  dx,
           If(d==2, -dy,
           If(d==3, -dx,
           If(d==4,  dy,
           If(d==5, -dx,
           If(d==6, -dy,
                     dx)))))))

def z3_min(*vals):
    m = vals[0]
    for v in vals[1:]: m = If(v < m, v, m)
    return m

def z3_max(*vals):
    m = vals[0]
    for v in vals[1:]: m = If(v > m, v, m)
    return m

# ==========================================
# PLACEMENT
# ==========================================
@dataclass
class Placement:
    x: ArithRef
    y: ArithRef
    ox: ArithRef
    oy: ArithRef
    w: ArithRef
    h: ArithRef
    d: ArithRef
    cuts: dict[str, ArithRef] = field(default_factory=dict)

    def aabb(self):
        c1 = (self.ox, self.oy)
        c2 = (self.ox + self.w - 1, self.oy)
        c3 = (self.ox, self.oy + self.h - 1)
        c4 = (self.ox + self.w - 1, self.oy + self.h - 1)

        wx1 = self.x + rot_x(c1[0], c1[1], self.d)
        wy1 = self.y + rot_y(c1[0], c1[1], self.d)
        wx2 = self.x + rot_x(c2[0], c2[1], self.d)
        wy2 = self.y + rot_y(c2[0], c2[1], self.d)
        wx3 = self.x + rot_x(c3[0], c3[1], self.d)
        wy3 = self.y + rot_y(c3[0], c3[1], self.d)
        wx4 = self.x + rot_x(c4[0], c4[1], self.d)
        wy4 = self.y + rot_y(c4[0], c4[1], self.d)

        min_x = z3_min(wx1, wx2, wx3, wx4)
        max_x = z3_max(wx1, wx2, wx3, wx4)
        min_y = z3_min(wy1, wy2, wy3, wy4)
        max_y = z3_max(wy1, wy2, wy3, wy4)
        return min_x, max_x, min_y, max_y

    def concrete_aabb(self, model) -> tuple[int, int, int, int]:
        min_x = model.evaluate(self.aabb()[0]).as_long()
        max_x = model.evaluate(self.aabb()[1]).as_long()
        min_y = model.evaluate(self.aabb()[2]).as_long()
        max_y = model.evaluate(self.aabb()[3]).as_long()
        return min_x, max_x, min_y, max_y

@dataclass
class Context:
    var: int = 0

# ==========================================
# GROUP TEMPLATE (constraint-building group)
# ==========================================
class GroupTemplate:
    def __init__(self, spec: GroupSpec, parent_bounds: tuple[int, int, int, int], solver: Solver, ctx: Context, inherited_color: RangeSpec = -1):
        self.spec = spec
        self.solver = solver
        self.ctx = ctx
        self.px, self.py, self.pw, self.ph = parent_bounds
        self.inherited_color = inherited_color

        pool = spec.get("pool", [])
        prefix = spec.get("prefix", [])
        pattern = spec.get("pattern", [])

        count_spec = spec.get("count", 1)
        self.min_count, self.max_count, self.step_count = parse_range(count_spec)
        self.count_var = Int(f"cnt_{ctx.var}"); ctx.var += 1
        add_range_constraint(self.count_var, count_spec, solver)

        self.instances: list[Placement] = []
        self.child_groups: list[list["GroupTemplate"]] = []
        self.link_parent_vars = []
        self.link_kind_vars = []

        self.resolved_color = spec.get("color", inherited_color)

        base_type = spec.get("type", "Geometry")
        base_size = spec.get("size", {})
        base_fill_color = spec.get("fill_color")
        base_vertice_color = spec.get("vertice_color")
        base_cut = spec.get("cut", {})
        base_dir = spec.get("dir", 0)
        base_geometries = spec.get("geometries", [])
        base_origin = spec.get("origin", {})

        self.margin = roll_range(spec.get("margin", 0))
        self.px += self.margin
        self.py += self.margin
        self.pw -= 2 * self.margin
        self.ph -= 2 * self.margin

        self.instance_types = []
        self.instance_colors = []
        self.instance_fill_colors = []
        self.instance_vertice_colors = []
        self.instance_origins = []
        self.instance_pool_indices = []

        singleton_first_vars = {}
        first_singleton_occurrence = {}

        for i in range(self.max_count):
            if i < len(prefix):
                idx = prefix[i]
            elif pattern:
                idx = pattern[(i - len(prefix)) % len(pattern)]
            else:
                idx = -1

            if idx == -1 or idx >= len(pool):
                base_w = spec.get("weight", 1)
                total_weight = base_w
                for p_item in pool:
                    w = p_item.get("weight", 0)
                    total_weight += w
                if total_weight == 0:
                    total_weight = 1
                    base_w = 1
                r = random.uniform(0, total_weight)
                idx = -1
                for p_index, p_item in enumerate(pool):
                    w = p_item.get("weight", 0)
                    if w <= 0: continue
                    if r < w:
                        ov_type = p_item.get("type", base_type)
                        if isinstance(ov_type, list): ov_type = random.choice(ov_type)
                        inst_size = p_item.get("size", base_size)
                        inst_color = p_item.get("color", self.resolved_color)
                        inst_fill_color = p_item.get("fill_color", base_fill_color)
                        inst_vertice_color = p_item.get("vertice_color", base_vertice_color)
                        inst_cut = p_item.get("cut", base_cut)
                        inst_dir = p_item.get("dir", base_dir)
                        inst_geometries = p_item.get("geometries", base_geometries)
                        inst_origin = p_item.get("origin", base_origin)
                        inst_type = ov_type
                        idx = p_index
                        break
                    r -= w
                if idx < 0:
                    inst_type = base_type if not isinstance(base_type, list) else random.choice(base_type)
                    inst_size = base_size
                    inst_color = self.resolved_color
                    inst_fill_color = base_fill_color
                    inst_vertice_color = base_vertice_color
                    inst_cut = base_cut
                    inst_dir = base_dir
                    inst_geometries = base_geometries
                    inst_origin = base_origin
            else:
                ov = pool[idx]
                inst_type = ov.get("type", base_type)
                if isinstance(inst_type, list): inst_type = random.choice(inst_type)
                inst_size = ov.get("size", base_size)
                inst_color = ov.get("color", self.resolved_color)
                inst_fill_color = ov.get("fill_color", base_fill_color)
                inst_vertice_color = ov.get("vertice_color", base_vertice_color)
                inst_cut = ov.get("cut", base_cut)
                inst_dir = ov.get("dir", base_dir)
                inst_geometries = ov.get("geometries", base_geometries)
                inst_origin = ov.get("origin", base_origin)

            self.instance_types.append(inst_type)
            self.instance_colors.append(inst_color)
            self.instance_fill_colors.append(inst_fill_color)
            self.instance_vertice_colors.append(inst_vertice_color)
            self.instance_origins.append(inst_origin)
            self.instance_pool_indices.append(idx)

            x = Int(f"x_{ctx.var}"); ctx.var += 1
            y = Int(f"y_{ctx.var}"); ctx.var += 1
            ox = Int(f"ox_{ctx.var}"); ctx.var += 1
            oy = Int(f"oy_{ctx.var}"); ctx.var += 1
            w = Int(f"w_{ctx.var}"); ctx.var += 1
            h = Int(f"h_{ctx.var}"); ctx.var += 1
            d = Int(f"d_{ctx.var}"); ctx.var += 1

            active = i < self.count_var
            solver.add(If(active,
                          And(ox <= 0, ox > -w, oy <= 0, oy > -h,
                              w >= 1, h >= 1, d >= 0, d <= 7),
                          And(ox == 0, oy == 0, x == 0, y == 0, w == 0, h == 0, d == 0)))

            solver.add(Implies(active, range_expr(d, inst_dir)))

            if "x" in inst_origin:
                solver.add(Implies(active, range_expr(-ox, inst_origin["x"])))
            else:
                solver.add(Implies(active, ox == -(w / 2)))
            if "y" in inst_origin:
                solver.add(Implies(active, range_expr(-oy, inst_origin["y"])))
            else:
                solver.add(Implies(active, oy == -(h / 2)))

            cuts: CutSpec = {}
            for corner in ("tl", "tr", "br", "bl"):
                cv = Int(f"cut_{corner}_{ctx.var}"); ctx.var += 1
                cuts[corner] = cv
                solver.add(Implies(active, range_expr(cv, inst_cut.get(corner, 0))))
                solver.add(Implies(active, cv >= 0))
            solver.add(Implies(active, cuts["tl"] + cuts["tr"] <= w - 1))
            solver.add(Implies(active, cuts["bl"] + cuts["br"] <= w - 1))
            solver.add(Implies(active, cuts["tl"] + cuts["bl"] <= h - 1))
            solver.add(Implies(active, cuts["tr"] + cuts["br"] <= h - 1))

            is_singleton = (idx != -1 and idx < len(pool) and pool[idx].get("singleton", False))
            if is_singleton:
                if idx not in first_singleton_occurrence:
                    first_singleton_occurrence[idx] = i
                    use_children = True
                else:
                    use_children = False
                if idx not in singleton_first_vars:
                    singleton_first_vars[idx] = (ox, oy, w, h, d, cuts)
                else:
                    f_ox, f_oy, f_w, f_h, f_d, f_cuts = singleton_first_vars[idx]
                    solver.add(Implies(active, And(ox == f_ox, oy == f_oy,
                                                   w == f_w, h == f_h, d == f_d,
                                                   *[cuts[c] == f_cuts[c] for c in cuts])))
            else:
                use_children = True

            inst = Placement(x, y, ox, oy, w, h, d, cuts=cuts)
            self.instances.append(inst)

            xmin, xmax, ymin, ymax = inst.aabb()
            solver.add(Implies(active, And(xmin >= self.px, xmax < self.px + self.pw,
                                           ymin >= self.py, ymax < self.py + self.ph)))

            ext_w = xmax - xmin + 1
            ext_h = ymax - ymin + 1
            solver.add(Implies(active, Or(
                And(Or(d==0, d==2, d==4, d==6), w == ext_w, h == ext_h),
                And(Or(d==1, d==3, d==5, d==7), w == ext_h, h == ext_w)
            )))

            child_list: list[GroupTemplate] = []
            if use_children:
                for child_spec in inst_geometries:
                    child = build_template(child_spec,
                                           parent_bounds=(ox, oy, w, h),
                                           solver=solver, ctx=ctx,
                                           inherited_color=inst_color)
                    child_list.append(child)
            self.child_groups.append(child_list)

            sz = inst_size
            if sz:
                xmin, xmax, ymin, ymax = inst.aabb()
                ext_w = xmax - xmin + 1
                ext_h = ymax - ymin + 1
                c = []
                if "width" in sz: c.append(range_expr(ext_w, sz["width"]))
                if "height" in sz: c.append(range_expr(ext_h, sz["height"]))
                if "top" in sz: c.append(range_expr(ymin - self.py, sz["top"]))
                if "bottom" in sz: c.append(range_expr(self.py + self.ph - 1 - ymax, sz["bottom"]))
                if "left" in sz: c.append(range_expr(xmin - self.px, sz["left"]))
                if "right" in sz: c.append(range_expr(self.px + self.pw - 1 - xmax, sz["right"]))
                if "min" in sz or "max" in sz:
                    min_spec = sz.get("min", [1, 1])
                    max_spec = sz.get("max", min_spec)
                    c.append(If(ext_w <= ext_h,
                                And(range_expr(ext_w, min_spec), range_expr(ext_h, max_spec)),
                                And(range_expr(ext_h, min_spec), range_expr(ext_w, max_spec))))
                if "ratio" in sz:
                    ratio_spec = sz["ratio"]
                    r_min, r_max, _ = parse_range(ratio_spec)
                    longer = If(ext_w > ext_h, ext_w, ext_h)
                    shorter = If(ext_w > ext_h, ext_h, ext_w)
                    c.append(And(longer >= shorter * r_min, longer <= shorter * r_max))
                if "area" in sz:
                    area_spec = sz["area"]
                    a_min, a_max, _ = parse_range(area_spec)
                    c.append(And(ext_w * ext_h >= a_min, ext_w * ext_h <= a_max))
                if c: solver.add(Implies(active, And(c)))
            elif inst_type == "Point":
                solver.add(Implies(active, And(inst.w == 1, inst.h == 1)))
            elif inst_type == "Line":
                solver.add(Implies(active, And(inst.h == 1)))

        self._add_strategy_constraints()

    def _add_link_options(self, i, j, cond, gvar, allowed_types, insts):
        adj = []
        a = insts[j]; b = insts[i]
        kind_var = self.link_kind_vars[i]
        a_min_x, a_max_x, a_min_y, a_max_y = a.aabb()
        b_min_x, b_max_x, b_min_y, b_max_y = b.aabb()

        if "Line" in allowed_types:
            adj.append(And(cond, kind_var == 0, b_min_x == a_max_x + gvar + 1, a_min_y <= b.y, b.y <= a_max_y))
            adj.append(And(cond, kind_var == 2, b_min_y == a_max_y + gvar + 1, a_min_x <= b.x, b.x <= a_max_x))
            adj.append(And(cond, kind_var == 4, a_min_x == b_max_x + gvar + 1, a_min_y <= b.y, b.y <= a_max_y))
            adj.append(And(cond, kind_var == 6, a_min_y == b_max_y + gvar + 1, a_min_x <= b.x, b.x <= a_max_x))
        if "Diagonal" in allowed_types:
            adj.append(And(cond, kind_var == 1, b_min_x == a_max_x + gvar + 1, b_min_y == a_max_y + gvar + 1, b.x - a_max_x == b.y - a_max_y))
            adj.append(And(cond, kind_var == 3, a_min_x == b_max_x + gvar + 1, b_min_y == a_max_y + gvar + 1, a_min_x - b.x == b.y - a_max_y))
            adj.append(And(cond, kind_var == 5, a_min_x == b_max_x + gvar + 1, a_min_y == b_max_y + gvar + 1, a_min_x - b.x == a_min_y - b.y))
            adj.append(And(cond, kind_var == 7, b_min_x == a_max_x + gvar + 1, a_min_y == b_max_y + gvar + 1, b.x - a_max_x == a_min_y - b.y))
        return adj

    def _add_strategy_constraints(self):
        if not self.instances:
            return

        strategy = self.spec.get("strategy", "random")
        gap = self.spec.get("gap", 0)
        max_n = self.max_count
        cnt = self.count_var
        insts = self.instances

        if strategy == "random":
            for i in range(max_n):
                for j in range(i + 1, max_n):
                    xi_min, xi_max, yi_min, yi_max = insts[i].aabb()
                    xj_min, xj_max, yj_min, yj_max = insts[j].aabb()
                    self.solver.add(
                        Implies(And(i < cnt, j < cnt),
                                Or(xi_max + gap < xj_min,
                                   xj_max + gap < xi_min,
                                   yi_max + gap < yj_min,
                                   yj_max + gap < yi_min)))
            return

        col = [Int(f"col_{self.ctx.var + i}") for i in range(max_n)]
        row = [Int(f"row_{self.ctx.var + max_n + i}") for i in range(max_n)]
        level = [Int(f"level_{self.ctx.var + 2 * max_n + i}") for i in range(max_n)]
        self.col_vars, self.row_vars, self.level_vars = col, row, level
        self.ctx.var += 3 * max_n
        for i in range(max_n):
            self.solver.add(If(i < cnt,
                And(row[i] >= 0, col[i] >= 0, level[i] >= 0),
                And(row[i] == 0, col[i] == 0, level[i] == 0)))
            self.solver.add(Implies(i < cnt, And([Or(row[i] != row[j], col[i] != col[j]) for j in range(i)])))
        self.solver.add(Or([0 == cnt] + [And(i < cnt, 0 == row[i]) for i in range(max_n)]))
        self.solver.add(Or([0 == cnt] + [And(i < cnt, 0 == col[i]) for i in range(max_n)]))
        self.solver.add(Or(0 == cnt, 0 == level[0]))

        if strategy == "flow":
            row_height = Int(f"rowh_{self.ctx.var}"); self.ctx.var += 1
            self.solver.add(row_height >= 0)
            heights = []
            for i in range(max_n):
                inst = insts[i]
                _, _, yi_min, yi_max = inst.aabb()
                h_i = yi_max - yi_min + 1
                heights.append(h_i)
                self.solver.add(Implies(i < cnt, h_i <= row_height))
            self.solver.add(Or([0 == cnt] + [And(i < cnt, row_height == heights[i]) for i in range(max_n)]))

            x0_min, _, y0_min, _ = insts[0].aabb()
            self.solver.add(Implies(0 < cnt, And(x0_min == self.px, y0_min == self.py)))

            for i in range(1, max_n):
                prev = insts[i-1]; curr = insts[i]
                _, prev_xmax, prev_ymin, _ = prev.aabb()
                curr_xmin, curr_xmax, curr_ymin, _ = curr.aabb()
                curr_width = curr_xmax - curr_xmin + 1
                fits = (prev_xmax + gap + 1 + curr_width <= self.px + self.pw)
                self.solver.add(Implies(i < cnt, curr_xmin == If(fits, prev_xmax + gap + 1, self.px)))
                self.solver.add(Implies(i < cnt, curr_ymin == If(fits, prev_ymin, prev_ymin + row_height + gap)))
                self.solver.add(Implies(i < cnt, row[i] == If(fits, row[i-1], row[i-1] + 1)))
                self.solver.add(Implies(i < cnt, col[i] == If(fits, col[i-1] + 1, 0)))
                self.solver.add(level[i] == row[i] + col[i])

            for i in range(max_n):
                inst = insts[i]
                _, _, _, yi_max = inst.aabb()
                self.solver.add(Implies(i < cnt, yi_max < self.py + self.ph))

        if strategy in ("tree", "chain"):
            link_spec = self.spec.get("link", {})
            allowed_types = link_spec.get("type", ["Line", "Diagonal"])
            if isinstance(allowed_types, str):
                allowed_types = [allowed_types]
            gap_spec = link_spec.get("gap", self.spec.get("gap", 0))
            self.link_kind_vars = [Int(f"link_kind_{self.ctx.var + i}") for i in range(max_n)]
            self.link_parent_vars = [Int(f"parent_{self.ctx.var + max_n + i}") for i in range(max_n)]
            self.ctx.var += 2 * max_n
            self.solver.add(Implies(0 < cnt, And(self.link_kind_vars[0] == 0, self.link_parent_vars[0] == 0)))
            for i in range(1, max_n):
                gvar = Int(f"link_gap_{self.ctx.var}"); self.ctx.var += 1
                self.solver.add(If(i < cnt, range_expr(gvar, gap_spec), gvar == 0))
                if strategy == "tree": parent_indices = range(i)
                elif strategy == "chain": parent_indices = [i - 1]
                kvar = self.link_kind_vars[i]
                pvar = self.link_parent_vars[i]
                self.solver.add(If(i < cnt, And(pvar >= 0, pvar < i), pvar == 0))
                self.solver.add(If(i < cnt, And(kvar >= 0, kvar < 8), kvar == 0))
                adj = []
                for j in parent_indices:
                    adj.extend(self._add_link_options(i, j, pvar == j, gvar, allowed_types, insts))
                self.solver.add(Implies(i < cnt, Or(adj)))

                self.solver.add(Implies(i < cnt, And(
                    Or([And(kvar == k, pvar == j, col[i] == col[j] + KIND_DCOL[k]) for k in range(8) for j in parent_indices]),
                    Or([And(kvar == k, pvar == j, row[i] == row[j] + KIND_DROW[k]) for k in range(8) for j in parent_indices]))))
                self.solver.add(Implies(i < cnt,
                    Or([And(pvar == j, level[i] == level[j] + 1) for j in parent_indices])))

            for i in range(1, max_n):
                for j in range(i):
                    if j > 0:
                        pi, pj = self.link_parent_vars[i], self.link_parent_vars[j]
                        self.solver.add(Implies(And(i < cnt, pi == pj),
                            self.link_kind_vars[i] < self.link_kind_vars[j]))
                    xi_min, xi_max, yi_min, yi_max = insts[i].aabb()
                    xj_min, xj_max, yj_min, yj_max = insts[j].aabb()
                    self.solver.add(Implies(i < cnt,
                        Or(xi_max + gap < xj_min,
                            xj_max + gap < xi_min,
                            yi_max + gap < yj_min,
                            yj_max + gap < yi_min)))

        def max_in_range(arr, range_spec):
            mvar = Int(f"max_{self.ctx.var}"); self.ctx.var += 1
            for i in range(max_n):
                self.solver.add(Implies(i < cnt, arr[i] <= mvar))
            self.solver.add(Implies(0 < cnt, Or([And(i < cnt, mvar == arr[i]) for i in range(max_n)])))
            self.solver.add(If(0 < cnt, range_expr(mvar, range_spec), mvar == 0))

        if "rows" in self.spec:
            max_in_range(row, self.spec["rows"])
        if "cols" in self.spec:
            max_in_range(col, self.spec["cols"])
        if "levels" in self.spec:
            max_in_range(level, self.spec["levels"])

    def create_instance(self, model) -> list[GeometrySpec]:
        spec = self.spec
        count_val = model[self.count_var].as_long()
        result = []
        singleton_children_cache = {}

        for i in range(count_val):
            inst = self.instances[i]
            x = model[inst.x].as_long()
            y = model[inst.y].as_long()
            ox = model[inst.ox].as_long()
            oy = model[inst.oy].as_long()
            w = model[inst.w].as_long()
            h = model[inst.h].as_long()
            d_val = model[inst.d].as_long()
            typ = self.instance_types[i]

            color = (roll_range(self.instance_colors[i]) if self.instance_colors[i] is not None
                     else roll_range(spec.get("color", self.inherited_color)))

            type_mapping = {
                "Rectangle": "Polygon",
            }

            item: GeometrySpec = {
                "type": type_mapping.get(typ, typ),
                "x": x, "y": y, "dir": d_val,
                "color": color,
                "geometries": []
            }
            if typ == "Rectangle":
                cut_vals = {c: model[v].as_long() for c, v in inst.cuts.items()}
                item["vertices"] = corner_points(ox, oy, w, h, cut_vals)
                if self.instance_fill_colors[i] is not None:
                    item["fill_color"] = roll_range(self.instance_fill_colors[i])
                if self.instance_vertice_colors[i] is not None:
                    item["vertice_color"] = roll_range(self.instance_vertice_colors[i])
            elif typ == "Line":
                item["ox"] = ox
                item["oy"] = oy
                item["length"] = w
            elif typ == "Diagonal":
                item["ox"] = ox
                item["oy"] = oy
                item["length"] = min(w, h)

            pool = spec.get("pool", [])
            idx = self.instance_pool_indices[i]
            if idx != -1 and idx < len(pool) and pool[idx].get("singleton", False):
                cache_key = (id(spec), idx)
                if cache_key not in singleton_children_cache:
                    children = []
                    for child_group in self.child_groups[i]:
                        children.extend(child_group.create_instance(model))
                    singleton_children_cache[cache_key] = children
                item["geometries"].extend(singleton_children_cache[cache_key])
            else:
                for child_group in self.child_groups[i]:
                    item["geometries"].extend(child_group.create_instance(model))

            inst_origin = self.instance_origins[i]
            if "x" in inst_origin or "y" in inst_origin:
                item["geometries"].append({
                    "type": "Point", "x": 0, "y": 0, "dir": 0,
                    "color": color, "geometries": []
                })

            result.append(item)

        if spec.get("strategy") in ("tree", "chain") and count_val > 1:
            link_spec = self.spec.get("link", {})
            links = self._extract_links(model, count_val)
            if link_spec.get("above", 0) == 0:
                result = links + result
            else:
                result.extend(links)
        return result

    def _extract_links(self, model, count_val: int) -> list[GeometrySpec]:
        geoms = []
        link_spec = self.spec.get("link", {})
        link_color = roll_range(link_spec.get("color", self.resolved_color))

        for i in range(1, count_val):
            child = self.instances[i]
            cx, cy = model[child.x].as_long(), model[child.y].as_long()

            j = model[self.link_parent_vars[i]].as_long()
            k = model[self.link_kind_vars[i]].as_long()

            parent = self.instances[j]
            px_min, px_max, py_min, py_max = parent.concrete_aabb(model)

            if k == 0:
                x0 = px_max + 1
                geoms.append({"type": "Line", "x": x0, "y": cy, "length": cx - x0 + 1, "dir": 0, "color": link_color})
            if k == 2:
                y0 = py_max + 1
                geoms.append({"type": "Line", "x": cx, "y": y0, "length": cy - y0 + 1, "dir": 1, "color": link_color})
            if k == 4:
                x0 = px_min - 1
                geoms.append({"type": "Line", "x": x0, "y": cy, "length": x0 - cx + 1, "dir": 2, "color": link_color})
            if k == 6:
                y0 = py_min - 1
                geoms.append({"type": "Line", "x": cx, "y": y0, "length": y0 - cy + 1, "dir": 3, "color": link_color})
            if k == 1:
                x0, y0 = px_max + 1, py_max + 1
                geoms.append({"type": "Diagonal", "x": x0, "y": y0, "length": cx - x0 + 1, "dir": 0, "color": link_color})
            if k == 3:
                x0, y0 = px_min - 1, py_max + 1
                geoms.append({"type": "Diagonal", "x": x0, "y": y0, "length": x0 - cx + 1, "dir": 1, "color": link_color})
            if k == 5:
                x0, y0 = px_min - 1, py_min - 1
                geoms.append({"type": "Diagonal", "x": x0, "y": y0, "length": x0 - cx + 1, "dir": 2, "color": link_color})
            if k == 7:
                x0, y0 = px_max + 1, py_min - 1
                geoms.append({"type": "Diagonal", "x": x0, "y": y0, "length": cx - x0 + 1, "dir": 3, "color": link_color})

        return geoms


def build_template(spec: GroupSpec, parent_bounds, solver: Solver, ctx: Context, inherited_color: RangeSpec = -1) -> GroupTemplate:
    return GroupTemplate(spec, parent_bounds, solver, ctx, inherited_color)


def generate_instance_spec(gen_spec: CanvasTemplateSpec) -> CanvasSpec:
    w_spec = gen_spec["width"]; h_spec = gen_spec["height"]
    back_spec = roll_range(gen_spec.get("background", 0))
    min_w = w_spec[0] if isinstance(w_spec, list) else w_spec
    max_w = w_spec[1] if isinstance(w_spec, list) else w_spec
    min_h = h_spec[0] if isinstance(h_spec, list) else h_spec
    max_h = h_spec[1] if isinstance(h_spec, list) else h_spec

    ctx = Context()
    solver = Solver()
    solver.set('random_seed', random.randint(0, 1000000))
    canvas_w = Int('canvas_w'); canvas_h = Int('canvas_h')
    solver.add(canvas_w >= min_w, canvas_w <= max_w)
    solver.add(canvas_h >= min_h, canvas_h <= max_h)

    root_templates = [
        build_template(layer_spec, parent_bounds=(0, 0, canvas_w, canvas_h), solver=solver, ctx=ctx, inherited_color=-1)
        for layer_spec in gen_spec["geometries"]
    ]

    if solver.check() == unsat:
        raise Exception("Constraints unsatisfiable – adjust spec ranges")
    model = solver.model()

    layers_geoms: list[GeometrySpec] = []
    for root in root_templates:
        layers_geoms.extend(root.create_instance(model))

    return {
        "width": model[canvas_w].as_long(),
        "height": model[canvas_h].as_long(),
        "background": back_spec,
        "geometries": layers_geoms,
    }
