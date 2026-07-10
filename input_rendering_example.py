import random
import numpy as np
from z3 import *
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.path import Path

# ==========================================
# 1. SHARED CONSTANTS & MATRICES
# ==========================================
DIR_MATRICES = [
    np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=int),
    np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=int),
    np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]], dtype=int),
    np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]], dtype=int),
    np.array([[0, 1, 0], [1, 0, 0], [0, 0, 1]], dtype=int),
    np.array([[-1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=int),
    np.array([[0, -1, 0], [-1, 0, 0], [0, 0, 1]], dtype=int),
    np.array([[1, 0, 0], [0, -1, 0], [0, 0, 1]], dtype=int),
]

ARC_COLORS = [
    '#000000', '#0074D9', '#FF4136', '#2ECC40', '#FFDC00',
    '#AAAAAA', '#F012BE', '#FF851B', '#7FDBFF', '#870C25'
]
ARC_CMAP = ListedColormap(ARC_COLORS)

# ==========================================
# 2. CORE RENDERING ENGINE
# ==========================================
class Geometry:
    def __init__(self, x=0, y=0, dir=0, color=None, geometries=None):
        self.x = x; self.y = y; self.dir = dir; self.color = color
        self.parent = None
        self.geometries = geometries or []
        for g in self.geometries: g.parent = self

    @property
    def local_matrix(self):
        return np.array([[1, 0, self.x], [0, 1, self.y], [0, 0, 1]], dtype=int) @ DIR_MATRICES[self.dir]

    @property
    def world_matrix(self):
        return self.parent.world_matrix @ self.local_matrix if self.parent else self.local_matrix

    def get_local_points(self): return []

class Point(Geometry):
    def get_local_points(self): return [(0, 0, self.color)]

class Line(Geometry):
    def __init__(self, x=0, y=0, dir=0, length=1, color=None, geometries=None):
        super().__init__(x, y, dir, color, geometries)
        self.length = length
    def get_local_points(self): return [(i, 0, self.color) for i in range(self.length)]

class Diagonal(Geometry):
    def __init__(self, x=0, y=0, dir=0, length=1, color=None, geometries=None):
        super().__init__(x, y, dir, color, geometries)
        self.length = length
    def get_local_points(self): return [(i, i, self.color) for i in range(self.length)]

class Polygon(Geometry):
    def __init__(self, x=0, y=0, dir=0, color=None, fill_color=None, vertices=None, geometries=None):
        super().__init__(x, y, dir, color, geometries)
        self.vertices = vertices or []
        self.fill_color = fill_color

    def get_local_points(self):
        if not self.vertices: return []
        points = {}
        path = Path(self.vertices)
        xs, ys = [v[0] for v in self.vertices], [v[1] for v in self.vertices]
        min_x, max_x, min_y, max_y = int(min(xs)), int(max(xs)), int(min(ys)), int(max(ys))
        int_color = self.fill_color if self.fill_color is not None else self.color
        for py in range(min_y, max_y+1):
            points[py] = {}
            for px in range(min_x, max_x+1):
                points[py][px] = -1
                if path.contains_point((px, py), radius=0.1): points[py][px] = int_color
        for i in range(len(self.vertices)):
            x0, y0 = self.vertices[i]; x1, y1 = self.vertices[i-1]
            if x0 == x1:
                for y in range(min(y0, y1), max(y0, y1)+1): points[y][x0] = self.color
            elif y0 == y1:
                for x in range(min(x0, x1), max(x0, x1)+1): points[y0][x] = self.color
        return [(x, y, points[y][x]) for y in points for x in points[y]]

class Canvas:
    @staticmethod
    def parse_geometry(g_spec):
        t = g_spec["type"]
        c = g_spec.get("color")
        x = g_spec.get("x", 0)
        y = g_spec.get("y", 0)
        d = g_spec.get("dir", 0)
        subs = [Canvas.parse_geometry(s) for s in g_spec.get("geometries", [])]
        if t == "Polygon": return Polygon(x=x, y=y, dir=d, color=c, fill_color=g_spec.get("fill_color"), vertices=g_spec.get("vertices", []), geometries=subs)
        elif t == "Line": return Line(x=x, y=y, dir=d, length=g_spec.get("length", 1), color=c, geometries=subs)
        elif t == "Diagonal": return Diagonal(x=x, y=y, dir=d, length=g_spec.get("length", 1), color=c, geometries=subs)
        elif t == "Point": return Point(x=x, y=y, dir=d, color=c, geometries=subs)
        return Geometry(x=x, y=y, dir=d, color=c, geometries=subs)

    @staticmethod
    def parse_canvas(spec):
        layers = [Canvas.parse_geometry(s) for s in spec.get("layers", [])]
        return Canvas(width=spec["width"], height=spec["height"], background=spec.get("background", 0), layers=layers)

    def __init__(self, width, height, background=0, layers=None):
        self.width, self.height, self.background = width, height, background
        self.layers = layers or []

    def render(self):
        grid = np.full((self.height, self.width), self.background, dtype=int)
        def collect(node, col):
            pts = []
            cur = getattr(node, 'color', None) or col
            if isinstance(node, Geometry):
                for px, py, c in node.get_local_points():
                    pts.append(((node.world_matrix @ [px, py, 1])[:2].tolist() + [c if c is not None else cur]))
            for ch in node.geometries: pts.extend(collect(ch, cur))
            return pts
        for layer in self.layers:
            for wx, wy, c in collect(layer, layer.color):
                if 0 <= wx < self.width and 0 <= wy < self.height and c not in (None, -1):
                    grid[wy, wx] = c
        return grid

# ==========================================
# 3. UNIFIED RANGE UTILITIES
# ==========================================
def parse_range(spec):
    if isinstance(spec, (int, float)):
        return int(spec), int(spec), 1
    if len(spec) == 2:
        return int(spec[0]), int(spec[1]), 1
    return int(spec[0]), int(spec[1]), int(spec[2])

def roll_range(spec):
    if isinstance(spec, (int, float)):
        return int(spec)
    lo, hi, step = parse_range(spec)
    if step == 1:
        return random.randint(lo, hi)
    n = (hi - lo) // step
    return lo + random.randint(0, n) * step

def add_range_constraint(var, spec, solver):
    lo, hi, step = parse_range(spec)
    solver.add(var >= lo, var <= hi)
    if step > 1:
        solver.add((var - lo) % step == 0)

def range_expr(var, spec):
    lo, hi, step = parse_range(spec)
    if step == 1:
        return And(var >= lo, var <= hi)
    return And(var >= lo, var <= hi, (var - lo) % step == 0)

# ==========================================
# 4. ROTATION HELPERS
# ==========================================
def rot_x(dx, dy, d):
    return If(d==0, dx,
           If(d==1, -dy,
           If(d==2, -dx,
           If(d==3,  dy,
           If(d==4,  dy,
           If(d==5, -dx,
           If(d==6, -dy,
                    dx)))))))

def rot_y(dx, dy, d):
    return If(d==0, dy,
           If(d==1,  dx,
           If(d==2, -dy,
           If(d==3, -dx,
           If(d==4,  dx,
           If(d==5,  dy,
           If(d==6, -dx,
                    -dy)))))))

def z3_min(*vals):
    m = vals[0]
    for v in vals[1:]: m = If(v < m, v, m)
    return m

def z3_max(*vals):
    m = vals[0]
    for v in vals[1:]: m = If(v > m, v, m)
    return m

# ==========================================
# 5. INSTANCE (with aabb)
# ==========================================
class Instance:
    def __init__(self, x, y, ox, oy, w, h, d):
        self.x = x; self.y = y
        self.ox = ox; self.oy = oy
        self.w = w; self.h = h
        self.d = d

    def aabb(self):
        """Axis‑aligned bounding box of the rotated shape in parent coords."""
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

    def concrete_aabb(self, model):
        """Evaluate AABB using the solved model (returns concrete ints)."""
        min_x = model.evaluate(self.aabb()[0]).as_long()
        max_x = model.evaluate(self.aabb()[1]).as_long()
        min_y = model.evaluate(self.aabb()[2]).as_long()
        max_y = model.evaluate(self.aabb()[3]).as_long()
        return min_x, max_x, min_y, max_y

    def expanded_aabb(self, margin):
        min_x, max_x, min_y, max_y = self.aabb()
        return min_x - margin, max_x + margin, min_y - margin, max_y + margin

# ==========================================
# 6. GROUP PLACEMENT ENGINE
# ==========================================
class GeneratorContext:
    def __init__(self):
        self.var = 0

class GroupPlacement:
    def __init__(self, spec, parent_bounds, solver, ctx, inherited_color=-1):
        self.spec = spec
        self.solver = solver
        self.ctx = ctx
        self.px, self.py, self.pw, self.ph = parent_bounds
        self.inherited_color = inherited_color

        self.pattern = spec.get("pattern", None)

        count_spec = spec.get("count", 1)
        self.min_count, self.max_count, self.step_count = parse_range(count_spec)
        self.count_var = Int(f"cnt_{ctx.var}"); ctx.var += 1
        add_range_constraint(self.count_var, count_spec, solver)

        self.instances = []
        self.child_groups = []
        self.link_vars = []

        self.resolved_color = spec["color"] if "color" in spec else inherited_color

        base_type = spec.get("type", "Geometry")
        base_size = spec.get("size", {})
        base_color = spec.get("color")
        base_dir = spec.get("dir", None)

        # --- margin ---
        margin_spec = spec.get("margin", 0)
        if isinstance(margin_spec, (int, float)):
            self.margin = int(margin_spec)
        elif isinstance(margin_spec, list):
            self.margin = roll_range(margin_spec)
        else:
            self.margin = 0

        self.instance_types = []
        self.instance_size_specs = []
        self.instance_colors = []

        def make_dir_constraint(dir_val):
            if dir_val is None:
                return None
            if isinstance(dir_val, int):
                return lambda d: (d == dir_val)
            if isinstance(dir_val, list):
                return lambda d: Or([d == v for v in dir_val])
            return None

        dir_constraint = make_dir_constraint(base_dir)

        for i in range(self.max_count):
            if self.pattern:
                pat = self.pattern[i % len(self.pattern)]
                inst_type = pat.get("type", base_type)
                if isinstance(inst_type, list): inst_type = random.choice(inst_type)
                inst_size = pat.get("size", base_size)
                inst_color = pat.get("color", base_color)
                pat_dir = pat.get("dir", base_dir)
                inst_dir_con = make_dir_constraint(pat_dir)
            else:
                inst_type = base_type if not isinstance(base_type, list) else random.choice(base_type)
                inst_size = base_size
                inst_color = base_color
                inst_dir_con = dir_constraint

            self.instance_types.append(inst_type)
            self.instance_size_specs.append(inst_size)
            self.instance_colors.append(inst_color)

            x = Int(f"x_{ctx.var}"); ctx.var += 1
            y = Int(f"y_{ctx.var}"); ctx.var += 1
            ox = Int(f"ox_{ctx.var}"); ctx.var += 1
            oy = Int(f"oy_{ctx.var}"); ctx.var += 1
            w = Int(f"w_{ctx.var}"); ctx.var += 1
            h = Int(f"h_{ctx.var}"); ctx.var += 1
            d = Int(f"d_{ctx.var}"); ctx.var += 1

            active = i < self.count_var
            solver.add(If(active,
                          And(ox <= 0, ox > -w,
                              oy <= 0, oy > -h,
                              w >= 1, h >= 1,
                              d >= 0, d <= 7),
                          And(ox == 0, oy == 0, x == 0, y == 0, w == 0, h == 0, d == 0)))

            if inst_dir_con is not None:
                solver.add(Implies(active, inst_dir_con(d)))

            inst = Instance(x, y, ox, oy, w, h, d)
            self.instances.append(inst)

            # Containment – use expanded AABB if margin > 0
            if self.margin > 0:
                exmin, exmax, eymin, eymax = inst.expanded_aabb(self.margin)
            else:
                exmin, exmax, eymin, eymax = inst.aabb()
            solver.add(Implies(active,
                And(exmin >= self.px,
                    exmax < self.px + self.pw,
                    eymin >= self.py,
                    eymax < self.py + self.ph)))

            # Link internal w,h to external dimensions based on orientation
            xmin, xmax, ymin, ymax = inst.aabb()
            ext_w = xmax - xmin + 1
            ext_h = ymax - ymin + 1
            solver.add(Implies(active,
                Or(
                    And(Or(d==0, d==2, d==5, d==7), w == ext_w, h == ext_h),
                    And(Or(d==1, d==3, d==4, d==6), w == ext_h, h == ext_w)
                )))

            # Children – placed in raw (unexpanded) bounding box
            child_list = []
            for child_spec in spec.get("geometries", []):
                child = GroupPlacement(child_spec,
                                       parent_bounds=(ox, oy, w, h),
                                       solver=solver, ctx=ctx,
                                       inherited_color=self.resolved_color)
                child_list.append(child)
            self.child_groups.append(child_list)

        # Size constraints on raw external dimensions
        for i in range(self.max_count):
            inst = self.instances[i]
            typ = self.instance_types[i]
            sz = self.instance_size_specs[i]
            active = i < self.count_var

            if typ == "Point" and not sz:
                solver.add(Implies(active, And(inst.w == 1, inst.h == 1)))
            elif sz:
                xmin, xmax, ymin, ymax = inst.aabb()
                ext_w = xmax - xmin + 1
                ext_h = ymax - ymin + 1
                c = []
                if "width" in sz: c.append(range_expr(ext_w, sz["width"]))
                if "height" in sz: c.append(range_expr(ext_h, sz["height"]))
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

        self._add_strategy_constraints()

    # ------------------------------------------------------------
    # Link options using AABB (works for any orientation)
    # ------------------------------------------------------------
    def _add_link_options(self, i, j, cond, lvar, allowed_types, insts):
        adj = []
        a = insts[j]   # parent
        b = insts[i]   # child

        a_min_x, a_max_x, a_min_y, a_max_y = a.aabb()
        b_min_x, b_max_x, b_min_y, b_max_y = b.aabb()

        if "Line" in allowed_types:
            adj.append(And(cond,
                           b_min_x == a_max_x + lvar + 1,
                           a_min_y < b_max_y, b_min_y < a_max_y))
            adj.append(And(cond,
                           a_min_x == b_max_x + lvar + 1,
                           a_min_y < b_max_y, b_min_y < a_max_y))
            adj.append(And(cond,
                           b_min_y == a_max_y + lvar + 1,
                           a_min_x < b_max_x, b_min_x < a_max_x))
            adj.append(And(cond,
                           a_min_y == b_max_y + lvar + 1,
                           a_min_x < b_max_x, b_min_x < a_max_x))

        if "Diagonal" in allowed_types:
            adj.append(And(cond,
                           b_min_x == a_max_x + lvar + 1,
                           b_min_y == a_max_y + lvar + 1))
            adj.append(And(cond,
                           b_max_x == a_min_x - lvar - 1,
                           b_min_y == a_max_y + lvar + 1))
            adj.append(And(cond,
                           a_min_x == b_max_x + lvar + 1,
                           a_min_y == b_max_y + lvar + 1))
            adj.append(And(cond,
                           b_min_x == a_max_x + lvar + 1,
                           b_max_y == a_min_y - lvar - 1))
        return adj

    def _add_strategy_constraints(self):
        if not self.instances:
            return

        strategy = self.spec.get("strategy", "random")
        gap = self.spec.get("gap", 0)
        max_n = self.max_count
        cnt = self.count_var
        insts = self.instances
        margin = self.margin

        # Helper: expanded AABB (with margin) for placement
        def aabb_edges(inst):
            if margin > 0:
                return inst.expanded_aabb(margin)
            else:
                return inst.aabb()

        # Global non‑overlap for random/tree/chain/star – uses expanded AABBs
        if strategy in ("random", "tree", "chain", "star"):
            for i in range(max_n):
                for j in range(i + 1, max_n):
                    xi_min, xi_max, yi_min, yi_max = aabb_edges(insts[i])
                    xj_min, xj_max, yj_min, yj_max = aabb_edges(insts[j])
                    self.solver.add(
                        Implies(And(i < cnt, j < cnt),
                                Or(xi_max + gap < xj_min,
                                   xj_max + gap < xi_min,
                                   yi_max + gap < yj_min,
                                   yj_max + gap < yi_min)))

        if strategy == "random":
            pass

        elif strategy == "row":
            for i in range(max_n):
                inst = insts[i]
                xi_min, xi_max, yi_min, yi_max = aabb_edges(inst)
                self.solver.add(Implies(i < cnt, yi_min == self.py))
                if i == 0:
                    self.solver.add(Implies(i < cnt, xi_min == self.px))
                else:
                    prev = insts[i-1]
                    _, prev_xmax, _, _ = aabb_edges(prev)
                    self.solver.add(Implies(i < cnt, xi_min == prev_xmax + gap + 1))
                self.solver.add(Implies(i < cnt, yi_max < self.py + self.ph))
                self.solver.add(Implies(i < cnt, xi_max < self.px + self.pw))

        elif strategy == "flow":
            row_height = Int(f"rowh_{self.ctx.var}"); self.ctx.var += 1
            self.solver.add(row_height >= 0)
            for i in range(max_n):
                inst = insts[i]
                _, _, yi_min, yi_max = aabb_edges(inst)
                self.solver.add(Implies(i < cnt, yi_max - yi_min + 1 <= row_height))

            first = insts[0]
            x0_min, _, y0_min, _ = aabb_edges(first)
            self.solver.add(Implies(0 < cnt, And(x0_min == self.px, y0_min == self.py)))

            for i in range(1, max_n):
                prev = insts[i-1]; curr = insts[i]
                _, prev_xmax, prev_ymin, _ = aabb_edges(prev)
                curr_xmin, curr_xmax, curr_ymin, _ = aabb_edges(curr)
                curr_width = curr_xmax - curr_xmin + 1
                fits = (prev_xmax + gap + 1 + curr_width <= self.px + self.pw)
                self.solver.add(
                    Implies(And((i-1) < cnt, i < cnt),
                            curr_xmin == If(fits, prev_xmax + gap + 1, self.px)))
                self.solver.add(
                    Implies(And((i-1) < cnt, i < cnt),
                            curr_ymin == If(fits, prev_ymin, prev_ymin + row_height + gap)))

            for i in range(max_n):
                inst = insts[i]
                _, _, _, yi_max = aabb_edges(inst)
                self.solver.add(Implies(i < cnt, yi_max < self.py + self.ph))

        elif strategy in ("tree", "chain", "star"):
            # links still use raw AABB
            link_spec = self.spec.get("link")
            if link_spec:
                allowed_types = link_spec.get("types", [link_spec.get("type", "Line")])
                for i in range(1, max_n):
                    lvar = Int(f"link_{self.ctx.var}"); self.ctx.var += 1
                    self.link_vars.append(lvar)
                    self.solver.add(Implies(i < cnt, range_expr(lvar, link_spec["length"])))
                    if strategy == "tree": parent_indices = range(i)
                    elif strategy == "chain": parent_indices = [i - 1]
                    elif strategy == "star": parent_indices = [0]
                    adj = []
                    for j in parent_indices:
                        cond = And(j < cnt, i < cnt)
                        adj.extend(self._add_link_options(i, j, cond, lvar, allowed_types, insts))
                    self.solver.add(Implies(i < cnt, Or(adj)))

    def extract_geometries(self, model):
        spec = self.spec
        count_val = model[self.count_var].as_long()
        result = []
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

            item = {
                "type": "Polygon",
                "x": x, "y": y, "dir": d_val,
                "color": color,
                "geometries": []
            }
            if typ == "Rectangle":
                item["vertices"] = [[ox, oy], [ox + w - 1, oy], [ox + w - 1, oy + h - 1], [ox, oy + h - 1]]
            elif typ == "Point":
                item = {"type": "Point", "x": x, "y": y, "dir": d_val, "color": color, "geometries": []}

            for child_group in self.child_groups[i]:
                item["geometries"].extend(child_group.extract_geometries(model))
            result.append(item)

        if spec.get("strategy") in ("tree", "chain", "star") and "link" in spec and count_val > 1:
            result.extend(self._extract_links(model, count_val))
        return result

    def _extract_links(self, model, count_val):
        geoms = []
        spec = self.spec
        link_spec = spec["link"]
        link_color = roll_range(link_spec.get("color", self.resolved_color))
        allowed_types = link_spec.get("types", [link_spec.get("type", "Line")])
        strategy = spec.get("strategy")

        for i in range(1, count_val):
            child = self.instances[i]
            cx_min, cx_max, cy_min, cy_max = child.concrete_aabb(model)
            lvar = self.link_vars[i - 1]
            link_len = model[lvar].as_long()
            found = False

            if strategy == "tree":
                parent_indices = list(range(i))
            elif strategy == "chain":
                parent_indices = [i - 1]
            elif strategy == "star":
                parent_indices = [0]
            else:
                continue

            for j in parent_indices:
                if found: break
                parent = self.instances[j]
                px_min, px_max, py_min, py_max = parent.concrete_aabb(model)

                if "Line" in allowed_types:
                    if cx_min == px_max + link_len + 1 and py_min < cy_max and cy_min < py_max:
                        start_y = max(cy_min, py_min) + (min(cy_max, py_max) - max(cy_min, py_min)) // 2
                        geoms.append({"type": "Line", "x": px_max + 1, "y": start_y,
                                      "length": link_len, "dir": 0, "color": link_color})
                        found = True; break
                    if px_min == cx_max + link_len + 1 and py_min < cy_max and cy_min < py_max:
                        start_y = max(cy_min, py_min) + (min(cy_max, py_max) - max(cy_min, py_min)) // 2
                        geoms.append({"type": "Line", "x": px_min - 1, "y": start_y,
                                      "length": link_len, "dir": 2, "color": link_color})
                        found = True; break
                    if cy_min == py_max + link_len + 1 and px_min < cx_max and cx_min < px_max:
                        start_x = max(cx_min, px_min) + (min(cx_max, px_max) - max(cx_min, px_min)) // 2
                        geoms.append({"type": "Line", "x": start_x, "y": py_max + 1,
                                      "length": link_len, "dir": 1, "color": link_color})
                        found = True; break
                    if py_min == cy_max + link_len + 1 and px_min < cx_max and cx_min < px_max:
                        start_x = max(cx_min, px_min) + (min(cx_max, px_max) - max(cx_min, px_min)) // 2
                        geoms.append({"type": "Line", "x": start_x, "y": py_min - 1,
                                      "length": link_len, "dir": 3, "color": link_color})
                        found = True; break

                if "Diagonal" in allowed_types and not found:
                    if cx_min == px_max + link_len + 1 and cy_min == py_max + link_len + 1:
                        geoms.append({"type": "Diagonal", "x": px_max + 1, "y": py_max + 1,
                                      "length": link_len, "dir": 0, "color": link_color})
                        found = True; break
                    if cx_max == px_min - link_len - 1 and cy_min == py_max + link_len + 1:
                        geoms.append({"type": "Diagonal", "x": px_min - 1, "y": py_max + 1,
                                      "length": link_len, "dir": 1, "color": link_color})
                        found = True; break
                    if px_min == cx_max + link_len + 1 and py_min == cy_max + link_len + 1:
                        geoms.append({"type": "Diagonal", "x": px_min - 1, "y": py_min - 1,
                                      "length": link_len, "dir": 2, "color": link_color})
                        found = True; break
                    if cx_min == px_max + link_len + 1 and cy_max == py_min - link_len - 1:
                        geoms.append({"type": "Diagonal", "x": px_max + 1, "y": py_min - 1,
                                      "length": link_len, "dir": 3, "color": link_color})
                        found = True; break
        return geoms

# ==========================================
# 7. MAIN GENERATOR
# ==========================================
class PuzzleGen:
    @staticmethod
    def roll(val, default_min=0, default_max=32):
        if isinstance(val, list):
            a, b = val
            if a is None: a = default_min
            if b is None: b = default_max
            return random.randint(min(a,b), max(a,b))
        return val

    @classmethod
    def generate_exact_spec(cls, gen_spec):
        w_spec = gen_spec["width"]; h_spec = gen_spec["height"]
        min_w = w_spec[0] if isinstance(w_spec, list) else w_spec
        max_w = w_spec[1] if isinstance(w_spec, list) else w_spec
        min_h = h_spec[0] if isinstance(h_spec, list) else h_spec
        max_h = h_spec[1] if isinstance(h_spec, list) else h_spec

        ctx = GeneratorContext()
        solver = Solver()
        solver.set('random_seed', random.randint(0, 1000000))
        canvas_w = Int('canvas_w'); canvas_h = Int('canvas_h')
        solver.add(canvas_w >= min_w, canvas_w <= max_w)
        solver.add(canvas_h >= min_h, canvas_h <= max_h)

        layer_groups = []
        for layer_spec in gen_spec["layers"]:
            layer_inherited = layer_spec["color"] if "color" in layer_spec else -1
            root_group = GroupPlacement(
                layer_spec,
                parent_bounds=(0, 0, canvas_w, canvas_h),
                solver=solver, ctx=ctx,
                inherited_color=layer_inherited
            )
            layer_groups.append((layer_spec, root_group))

        if solver.check() == unsat:
            raise Exception("Constraints unsatisfiable – adjust spec ranges")
        model = solver.model()

        canvas_w_val = model[canvas_w].as_long()
        canvas_h_val = model[canvas_h].as_long()

        layers_geoms = []
        for layer_spec, root_group in layer_groups:
            layers_geoms.append({
                "type": "Geometry",
                "x": 0, "y": 0, "dir": 0,
                "color": roll_range(layer_spec["color"]) if "color" in layer_spec else -1,
                "geometries": root_group.extract_geometries(model)
            })

        return {
            "width": canvas_w_val,
            "height": canvas_h_val,
            "background": 0,
            "layers": layers_geoms
        }

# ==========================================
# 8. EXECUTION
# ==========================================
if __name__ == "__main__":
    generative_spec = {
        "type": "Canvas",
        "width": [16, 32],
        "height": [16, 32],
        "layers": [
            {
                "color": 1,
                "count": 0, #[2, 5],
                "gap": 2,
                "size": {"min": [3, 9], "max": [7, 15]},
                "strategy": "random",
                "type": "Geometry",
                "geometries": [
                    {
                        "count": [2, 9],
                        "gap": 1,
                        "link": {
                            "types": ["Line", "Diagonal"],
                            "length": [1, 3],
                            "color": 2
                        },
                        "size": {"min": [3, 5], "max": [3, 9]},
                        "strategy": "tree",
                        "type": "Rectangle",
                    },
                    {
                        "type": "Point",
                        "count": 1,
                        "color": [2, 9]
                    }
                ]
            },
            {
                "color": 2,
                "count": 3,
                "gap": 2,
                "margin": 2,
                "size": {
                    "width": 10,
                    "height": 7,
                },
                "strategy": "flow",
                "type": "Rectangle",
                "geometries": [
                    {
                        "type": "Rectangle",
                        "size": {
                            "width": [1, 1],
                            "height": [2, 2],
                        },
                        "gap": 1,
                        "margin": 1,
                        "strategy": "flow",
                        "count": [2, 7, 2],
                        "color": 3
                    }
                ]
            }
        ]
    }

    exact = PuzzleGen.generate_exact_spec(generative_spec)
    grid_in = Canvas.parse_canvas(exact).render()

    def fill_container(node):
        point_color = None
        polys = []
        for g in node.get("geometries", []):
            if g["type"] == "Point":
                point_color = g["color"]
                g["color"] = -1
            elif g["type"] == "Polygon":
                polys.append(g)
            elif "geometries" in g:
                fill_container(g)
        if point_color is not None:
            for p in polys:
                p["fill_color"] = point_color

    for layer in exact["layers"]:
        fill_container(layer)

    grid_out = Canvas.parse_canvas(exact).render()

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    axes[0].imshow(grid_in, cmap=ARC_CMAP, vmin=0, vmax=9)
    axes[0].set_title("Input")
    axes[1].imshow(grid_out, cmap=ARC_CMAP, vmin=0, vmax=9)
    axes[1].set_title("Output")
    for ax in axes:
        ax.grid(True, color='#555', linewidth=1)
        ax.set_xticks(np.arange(-0.5, exact['width'], 1), [])
        ax.set_yticks(np.arange(-0.5, exact['height'], 1), [])
    plt.tight_layout()
    plt.savefig("rendering_example.png")
    print("Done. See rendering_example.png")
