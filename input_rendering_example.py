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
# 4. Z3-BASED GROUP PLACEMENT ENGINE
# ==========================================
class Instance:
    def __init__(self, x, y, w, h):
        self.x = x; self.y = y; self.w = w; self.h = h

class GeneratorContext:
    def __init__(self):
        self.var = 0

class GroupPlacement:
    def __init__(self, spec, parent_bounds, solver, ctx, inherited_color=None):
        self.spec = spec
        self.solver = solver
        self.ctx = ctx
        self.px, self.py, self.pw, self.ph = parent_bounds
        self.inherited_color = inherited_color

        count_spec = spec.get("count", 1)
        self.min_count, self.max_count, self.step_count = parse_range(count_spec)
        self.count_var = Int(f"cnt_{ctx.var}"); ctx.var += 1
        add_range_constraint(self.count_var, count_spec, solver)

        self.instances = []
        self.child_groups = []
        self.link_vars = []

        if "color" in spec:
            self.resolved_color = spec["color"]
        else:
            self.resolved_color = inherited_color

        type_val = spec.get("type", "Geometry")
        if isinstance(type_val, list):
            self.instance_types = [random.choice(type_val) for _ in range(self.max_count)]
        else:
            self.instance_types = [type_val] * self.max_count

        size_spec = spec.get("size", {})

        for i in range(self.max_count):
            x = Int(f"x_{ctx.var}"); ctx.var += 1
            y = Int(f"y_{ctx.var}"); ctx.var += 1
            w = Int(f"w_{ctx.var}"); ctx.var += 1
            h = Int(f"h_{ctx.var}"); ctx.var += 1

            active = i < self.count_var
            solver.add(If(active,
                          And(x >= self.px, y >= self.py,
                              x + w <= self.px + self.pw,
                              y + h <= self.py + self.ph,
                              w >= 1, h >= 1),
                          And(x == 0, y == 0, w == 0, h == 0)))

            inst = Instance(x, y, w, h)
            self.instances.append(inst)

            child_list = []
            for child_spec in spec.get("geometries", []):
                child = GroupPlacement(child_spec,
                                       parent_bounds=(x, y, w, h),
                                       solver=solver, ctx=ctx,
                                       inherited_color=self.resolved_color)
                child_list.append(child)
            self.child_groups.append(child_list)

        # Size / default 1x1 for Point
        for i in range(self.max_count):
            w_var = self.instances[i].w
            h_var = self.instances[i].h
            typ = self.instance_types[i]

            if typ == "Point" and not size_spec:
                solver.add(Implies(i < self.count_var, And(w_var == 1, h_var == 1)))
            elif size_spec:
                c = []
                if "width" in size_spec:
                    c.append(range_expr(w_var, size_spec["width"]))
                if "height" in size_spec:
                    c.append(range_expr(h_var, size_spec["height"]))
                if "min" in size_spec or "max" in size_spec:
                    min_spec = size_spec.get("min", [1, 1])
                    max_spec = size_spec.get("max", min_spec)
                    c.append(If(w_var <= h_var,
                                And(range_expr(w_var, min_spec), range_expr(h_var, max_spec)),
                                And(range_expr(h_var, min_spec), range_expr(w_var, max_spec))))
                if c:
                    solver.add(Implies(i < self.count_var, And(c)))

        self._add_strategy_constraints()

    def _add_link_options(self, i, j, cond, lvar, allowed_types, insts):
        """Add adjacency constraints between instance i and instance j."""
        adj = []
        a = insts[j]
        b = insts[i]
        if "Line" in allowed_types:
            adj.append(And(cond, b.x == a.x + a.w + lvar,
                        a.y < b.y + b.h, b.y < a.y + a.h))
            adj.append(And(cond, a.x == b.x + b.w + lvar,
                        a.y < b.y + b.h, b.y < a.y + a.h))
            adj.append(And(cond, b.y == a.y + a.h + lvar,
                        a.x < b.x + b.w, b.x < a.x + a.w))
            adj.append(And(cond, a.y == b.y + b.h + lvar,
                        a.x < b.x + b.w, b.x < a.x + a.w))
        if "Diagonal" in allowed_types:
            # 1. Child down‑right (↘) : child.top-left = parent.bottom-right + (lvar, lvar)
            adj.append(And(cond, b.x == a.x + a.w + lvar,
                        b.y == a.y + a.h + lvar))
            # 2. Child down‑left  (↙) : child.top-right = parent.bottom-left + (-lvar, lvar)
            adj.append(And(cond, b.x + b.w == a.x - lvar,
                        b.y == a.y + a.h + lvar))
            # 3. Child up‑left    (↖) : child.bottom-right = parent.top-left + (-lvar, -lvar)
            adj.append(And(cond, a.x == b.x + b.w + lvar,
                        a.y == b.y + b.h + lvar))
            # 4. Child up‑right   (↗) : child.bottom-left = parent.top-right + (lvar, -lvar)
            adj.append(And(cond, b.x == a.x + a.w + lvar,
                        b.y + b.h == a.y - lvar))
        return adj

    def _add_strategy_constraints(self):
        strategy = self.spec.get("strategy", "random")
        gap = self.spec.get("gap", 0)
        max_n = self.max_count
        cnt = self.count_var
        insts = self.instances

        if strategy in ("random", "tree", "chain", "star"):
            for i in range(max_n):
                for j in range(i + 1, max_n):
                    a, b = insts[i], insts[j]
                    self.solver.add(
                        Implies(And(i < cnt, j < cnt),
                                Or(a.x + a.w + gap <= b.x,
                                   b.x + b.w + gap <= a.x,
                                   a.y + a.h + gap <= b.y,
                                   b.y + b.h + gap <= a.y)))

        if strategy == "random":
            pass

        elif strategy == "row":
            for i in range(max_n):
                self.solver.add(Implies(i < cnt, insts[i].y == self.py))
                if i == 0:
                    self.solver.add(Implies(i < cnt, insts[i].x == self.px))
                else:
                    self.solver.add(Implies(i < cnt,
                                            insts[i].x == insts[i-1].x + insts[i-1].w + gap))
                self.solver.add(Implies(i < cnt, insts[i].y + insts[i].h <= self.py + self.ph))
                self.solver.add(Implies(i < cnt, insts[i].x + insts[i].w <= self.px + self.pw))

        elif strategy == "flow":
            row_height = Int(f"rowh_{self.ctx.var}"); self.ctx.var += 1
            self.solver.add(row_height >= 0)
            for i in range(max_n):
                self.solver.add(Implies(i < cnt, insts[i].h <= row_height))
            self.solver.add(Implies(0 < cnt, And(insts[0].x == self.px, insts[0].y == self.py)))
            for i in range(1, max_n):
                a = insts[i-1]; b = insts[i]
                fits = (a.x + a.w + gap + b.w <= self.px + self.pw)
                self.solver.add(
                    Implies(And((i-1) < cnt, i < cnt),
                            b.x == If(fits, a.x + a.w + gap, self.px)))
                self.solver.add(
                    Implies(And((i-1) < cnt, i < cnt),
                            b.y == If(fits, a.y, a.y + row_height + gap)))
            for i in range(max_n):
                self.solver.add(Implies(i < cnt, insts[i].y + row_height <= self.py + self.ph))

        elif strategy in ("tree", "chain", "star"):
            link_spec = self.spec.get("link")
            if link_spec:
                allowed_types = link_spec.get("types", [link_spec.get("type", "Line")])
                for i in range(1, max_n):
                    lvar = Int(f"link_{self.ctx.var}"); self.ctx.var += 1
                    self.link_vars.append(lvar)
                    self.solver.add(Implies(i < cnt, range_expr(lvar, link_spec["length"])))

                    if strategy == "tree":
                        parent_indices = range(i)
                    elif strategy == "chain":
                        parent_indices = [i - 1]
                    elif strategy == "star":
                        parent_indices = [0]

                    adj = []
                    for j in parent_indices:
                        cond = And(j < cnt, i < cnt)
                        adj.extend(self._add_link_options(i, j, cond, lvar, allowed_types, insts))
                    self.solver.add(Implies(i < cnt, Or(adj)))

    def extract_geometries(self, model, offset_x=0, offset_y=0):
        spec = self.spec
        count_val = model[self.count_var].as_long()
        result = []

        for i in range(count_val):
            inst = self.instances[i]
            ix = model[inst.x].as_long()
            iy = model[inst.y].as_long()
            iw = model[inst.w].as_long()
            ih = model[inst.h].as_long()
            typ = self.instance_types[i]

            if "color" in spec:
                color = roll_range(spec["color"])
            else:
                color = roll_range(self.inherited_color) if self.inherited_color is not None else -1

            if typ == "Rectangle":
                x = ix - offset_x
                y = iy - offset_y
                result.append({
                    "type": "Polygon",
                    "vertices": [[x, y], [x + iw - 1, y], [x + iw - 1, y + ih - 1], [x, y + ih - 1]],
                    "color": color
                })
            elif typ == "Point":
                result.append({"type": "Point", "x": ix - offset_x, "y": iy - offset_y, "color": color})
            elif typ == "Line":
                result.append({"type": "Line", "x": ix - offset_x, "y": iy - offset_y,
                               "length": iw, "dir": 0, "color": color})

            if self.child_groups[i]:
                child_list = []
                for child_group in self.child_groups[i]:
                    child_list.extend(child_group.extract_geometries(model, offset_x=ix, offset_y=iy))
                if typ == "Geometry":
                    result.append({
                        "type": "Geometry",
                        "x": ix - offset_x,
                        "y": iy - offset_y,
                        "color": color,
                        "geometries": child_list
                    })
                else:
                    result.extend(child_list)

        if spec.get("strategy") in ("tree", "chain", "star") and "link" in spec and count_val > 1:
            link_geoms = self._extract_links(model, count_val, offset_x, offset_y)
            result.extend(link_geoms)

        return result

    def _extract_links(self, model, count_val, offset_x, offset_y):
        geoms = []
        spec = self.spec
        link_spec = spec["link"]
        if "color" in link_spec:
            link_color = roll_range(link_spec["color"])
        else:
            link_color = roll_range(self.resolved_color) if self.resolved_color is not None else -1
        allowed_types = link_spec.get("types", [link_spec.get("type", "Line")])
        strategy = spec.get("strategy")

        for i in range(1, count_val):
            child = self.instances[i]
            cx = model[child.x].as_long() - offset_x
            cy = model[child.y].as_long() - offset_y
            cw = model[child.w].as_long()
            ch = model[child.h].as_long()
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
                px = model[parent.x].as_long() - offset_x
                py = model[parent.y].as_long() - offset_y
                pw = model[parent.w].as_long()
                ph = model[parent.h].as_long()

                # ---- Orthogonal Links ----
                if "Line" in allowed_types:
                    # right of parent
                    if cx == px + pw + link_len and cy + ch > py and py + ph > cy:
                        start_y = max(cy, py) + (min(cy + ch, py + ph) - max(cy, py)) // 2
                        geoms.append({"type": "Line", "x": px + pw, "y": start_y,
                                    "length": link_len, "dir": 0, "color": link_color})
                        found = True; break
                    # left of parent
                    if px == cx + cw + link_len and cy + ch > py and py + ph > cy:
                        start_y = max(cy, py) + (min(cy + ch, py + ph) - max(cy, py)) // 2
                        geoms.append({"type": "Line", "x": px - 1, "y": start_y,
                                    "length": link_len, "dir": 2, "color": link_color})
                        found = True; break
                    # below parent
                    if cy == py + ph + link_len and cx + cw > px and px + pw > cx:
                        start_x = max(cx, px) + (min(cx + cw, px + pw) - max(cx, px)) // 2
                        geoms.append({"type": "Line", "x": start_x, "y": py + ph,
                                    "length": link_len, "dir": 1, "color": link_color})
                        found = True; break
                    # above parent
                    if py == cy + ch + link_len and cx + cw > px and px + pw > cx:
                        start_x = max(cx, px) + (min(cx + cw, px + pw) - max(cx, px)) // 2
                        geoms.append({"type": "Line", "x": start_x, "y": py - 1,
                                    "length": link_len, "dir": 3, "color": link_color})
                        found = True; break

                # ---- Diagonal Links ----
                if "Diagonal" in allowed_types and not found:
                    # 1. Child down‑right (↘) : start at parent bottom‑right outside corner
                    if cx == px + pw + link_len and cy == py + ph + link_len:
                        geoms.append({"type": "Diagonal", "x": px + pw, "y": py + ph,
                                    "length": link_len, "dir": 0, "color": link_color})
                        found = True; break
                    # 2. Child down‑left (↙) : start at parent bottom‑left outside corner
                    if cx + cw == px - link_len and cy == py + ph + link_len:
                        geoms.append({"type": "Diagonal", "x": px - 1, "y": py + ph,
                                    "length": link_len, "dir": 1, "color": link_color})
                        found = True; break
                    # 3. Child up‑left (↖) : start at parent top‑left outside corner
                    if px == cx + cw + link_len and py == cy + ch + link_len:
                        geoms.append({"type": "Diagonal", "x": px - 1, "y": py - 1,
                                    "length": link_len, "dir": 2, "color": link_color})
                        found = True; break
                    # 4. Child up‑right (↗) : start at parent top‑right outside corner
                    if cx == px + pw + link_len and cy + ch == py - link_len:
                        geoms.append({"type": "Diagonal", "x": px + pw, "y": py - 1,
                                    "length": link_len, "dir": 3, "color": link_color})
                        found = True; break
        return geoms

# ==========================================
# 5. MAIN GENERATOR
# ==========================================
class PuzzleGen:
    @staticmethod
    def roll(val, default_min=0, default_max=32):
        if isinstance(val, list):
            a, b = val
            if a is None: a = default_min
            if b is None: b = default_max
            return random.randint(min(a, b), max(a, b))
        return val

    @classmethod
    def generate_exact_spec(cls, gen_spec):
        w_spec = gen_spec["width"]
        h_spec = gen_spec["height"]
        min_w = w_spec[0] if isinstance(w_spec, list) else w_spec
        max_w = w_spec[1] if isinstance(w_spec, list) else w_spec
        min_h = h_spec[0] if isinstance(h_spec, list) else h_spec
        max_h = h_spec[1] if isinstance(h_spec, list) else h_spec

        ctx = GeneratorContext()
        solver = Solver()
        solver.set('random_seed', random.randint(0, 1000000))
        canvas_w = Int('canvas_w')
        canvas_h = Int('canvas_h')
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
            extracted = root_group.extract_geometries(model, offset_x=0, offset_y=0)
            layer_color = roll_range(layer_spec["color"]) if "color" in layer_spec else -1
            layers_geoms.append({
                "type": layer_spec.get("type", "Geometry"),
                "x": 0, "y": 0,
                "dir": 0,
                "color": layer_color,
                "geometries": extracted
            })

        return {
            "width": canvas_w_val,
            "height": canvas_h_val,
            "background": 0,
            "layers": layers_geoms
        }

# ==========================================
# 6. EXECUTION
# ==========================================
if __name__ == "__main__":
    generative_spec = {
        "type": "Canvas",
        "width": [16, 32],
        "height": [16, 32],
        "layers": [
            {
                "color": 1,
                "count": 0,
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
                            "length": [1, 3]
                        },
                        "size": {"min": [3, 5], "max": [3, 9]},
                        "strategy": "tree",
                        "type": ["Rectangle", "Point"]
                    },
                    {
                        "type": "Point",
                        "count": 1,
                        "color": [2, 9]
                    }
                ]
            },
            {
                "count": 25,
                "gap": 2,
                "size": {"width": [1, 3], "height": [2, 5]},
                "strategy": "flow",
                "type": "Rectangle"
            },
            {
                "color": 9,
                "count": 9,
                "gap": 1,
                "size": {"width": [2, 2], "height": [2, 2]},
                "strategy": "tree",
                "link": {
                    "types": ["Line", "Diagonal"],
                    "length": [2, 3],
                    "color": 5,
                },
                "type": "Rectangle"
            }
        ]
    }

    exact = PuzzleGen.generate_exact_spec(generative_spec)
    grid_in = Canvas.parse_canvas(exact).render()

    # Fill each cluster with its own point's color
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
