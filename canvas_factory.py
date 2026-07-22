import random
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, TypedDict
import cattrs
from z3 import Int, And, Or, If, Implies, ModelRef
from size_and_range import RangeSpec, SizeSpec, parse_range, range_expr, size_constraints
from bounded_solver import BoundedSolver

KIND_DCOL = {0: 1, 1: 1, 2: 0, 3: -1, 4: -1, 5: -1, 6: 0, 7: 1}
KIND_DROW = {0: 0, 1: 1, 2: 1, 3: 1, 4: 0, 5: -1, 6: -1, 7: -1}

TypeSpec = Literal["None", "Line", "Point", "Polygon"]

class CutSpec(TypedDict, total=False):
    tl: RangeSpec
    tr: RangeSpec
    br: RangeSpec
    bl: RangeSpec

class OriginSpec(TypedDict, total=False):
    x: RangeSpec
    y: RangeSpec
    color: RangeSpec

class DimensionSpec(TypedDict, total=False):
    count: RangeSpec
    gap: RangeSpec
    prefix: list[int]
    pattern: list[int]

class AlignmentSpec(TypedDict, total=False):
    top: bool
    bottom: bool
    left: bool
    right: bool

class GridSpec(TypedDict, total=False):
    cell_alignment: AlignmentSpec
    dir: RangeSpec
    primary_dir: int
    levels: DimensionSpec
    rows: DimensionSpec
    cols: DimensionSpec
    color: RangeSpec
    above: bool

class GeometryTemplateSpec(TypedDict, total=False):
    template: str
    type: TypeSpec
    size: SizeSpec
    color: RangeSpec
    edge_color: RangeSpec
    vertice_color: RangeSpec
    cut: CutSpec
    geometries: list["GeometryGroupSpec"]

class GeometryReferenceSpec(GeometryTemplateSpec, total=False):
    template: str
    tag: str
    dir: RangeSpec
    origin: OriginSpec

class GeometryGroupSpec(DimensionSpec, GeometryReferenceSpec, total=False):
    margin: RangeSpec
    grid: GridSpec
    pool: list[GeometryReferenceSpec]

class CanvasFactorySpec(TypedDict):
    root: str
    templates: dict[str, GeometryTemplateSpec]

@dataclass
class GeometryReference:
    template: Optional[str] = None
    tag: Optional[str] = None
    dir: Optional[RangeSpec] = None
    origin: Optional[OriginSpec] = None
    overrides: dict[str, Any] = field(default_factory=dict)
    size: SizeSpec = field(default_factory=dict, init=False, repr=False, compare=False)

    def generate_child_models(self, width: int, height: int,
                         rng: Optional[random.Random] = None) -> list["ModelRef"]:
        return [g.generate_model(width, height, rng) for g in self.overrides.get("geometries", [])]

@dataclass
class DimensionData:
    count: Optional[RangeSpec] = None
    gap: Optional[RangeSpec] = None
    prefix: list[int] = field(default_factory=list)
    pattern: list[int] = field(default_factory=list)

@dataclass
class GridData:
    dir: Optional[RangeSpec] = None
    primary_dir: Optional[int] = None
    levels: Optional[DimensionData] = None
    rows: Optional[DimensionData] = None
    cols: Optional[DimensionData] = None
    color: RangeSpec = -1
    above: bool = False
    cell_alignment: dict = field(default_factory=dict)

@dataclass
class GeometryGroup(BoundedSolver):
    template: Optional[str] = None
    tag: Optional[str] = None
    dir: RangeSpec = 0
    origin: OriginSpec = field(default_factory=dict)
    count: RangeSpec = 1
    prefix: list[int] = field(default_factory=list)
    pattern: list[int] = field(default_factory=list)
    gap: RangeSpec = 0
    margin: RangeSpec = 0
    grid: Optional[GridData] = None
    pool: list[GeometryReference] = field(default_factory=list)

    size: SizeSpec = field(default_factory=dict, init=False, repr=False, compare=False)

    def resolve(self, ref: GeometryReference) -> GeometryReference:
        return GeometryReference(
            template=ref.template if ref.template is not None else self.template,
            tag=ref.tag if ref.tag is not None else self.tag,
            dir=ref.dir if ref.dir is not None else self.dir,
            origin=ref.origin if ref.origin is not None else self.origin,
            overrides=ref.overrides,
        )
    
    def get_prefix(self):
        return f"{id(self)} group of {self.count} {self.template}"

    def add_constraints(self):
        prefix = self.get_prefix()
        solver = self.solver
        _, max_n, _ = parse_range(self.count)
        cnt = Int(f"{prefix}.cnt")
        solver.add(range_expr(cnt, self.count))
        gap = Int(f"{prefix}.gap"); solver.add(range_expr(gap, self.gap))
        margin = Int(f"{prefix}.margin"); solver.add(range_expr(margin, self.margin))

        x = [Int(f"{prefix}[{i}].x") for i in range(max_n)]
        y = [Int(f"{prefix}[{i}].y") for i in range(max_n)]
        w = [Int(f"{prefix}[{i}].w") for i in range(max_n)]
        h = [Int(f"{prefix}[{i}].h") for i in range(max_n)]
        slot = [Int(f"{prefix}[{i}].slot") for i in range(max_n)]
        for i in range(max_n):
            if self.prefix and i < len(self.prefix):
                value = self.prefix[i]
                value = value if value < len(self.pool) else -1
                solver.add(slot[i] == value)
            elif self.pattern and (i - len(self.prefix)) >= 0:
                value = self.pattern[(i - len(self.prefix)) % len(self.pattern)]
                value = value if value < len(self.pool) else -1
                solver.add(slot[i] == value)
            else:
                solver.add(And(slot[i] >= -1, slot[i] < len(self.pool)))

        result = {"cnt": cnt, "x": x, "y": y, "w": w, "h": h, "slot": slot}

        grid = self.grid
        if grid is not None:
            row = [Int(f"{prefix}[{i}].row") for i in range(max_n)]
            col = [Int(f"{prefix}[{i}].col") for i in range(max_n)]
            level = [Int(f"{prefix}[{i}].level") for i in range(max_n)]
            parent = [Int(f"{prefix}[{i}].parent") for i in range(max_n)]
            kind = [Int(f"{prefix}[{i}].kind") for i in range(max_n)]
            result.update(row=row, col=col, level=level, parent=parent, kind=kind)

            solver.add(level[0] == 0, parent[0] == -1, kind[0] == -1)
            solver.add(Or(cnt == 0, *[And(i < cnt, row[i] == 0) for i in range(max_n)]))
            solver.add(Or(cnt == 0, *[And(i < cnt, col[i] == 0) for i in range(max_n)]))
            for i in range(max_n):
                solver.add(row[i] < max_n, col[i] < max_n, level[i] < max_n)

            rows_gap_set = grid.rows is not None and grid.rows.gap is not None
            cols_gap_set = grid.cols is not None and grid.cols.gap is not None
            row_gap = Int(f"{prefix}.rows.gap")
            solver.add(range_expr(row_gap, grid.rows.gap if rows_gap_set else 0))
            col_gap = Int(f"{prefix}.cols.gap")
            solver.add(range_expr(col_gap, grid.cols.gap if cols_gap_set else 0))

            dim_count_vars = {}
            for dim_name, var_list in (("rows", row), ("cols", col), ("levels", level)):
                dim_data = getattr(grid, dim_name)
                if dim_data is not None and dim_data.count is not None:
                    count_var = Int(f"{prefix}.{dim_name}.count")
                    solver.add(range_expr(count_var, dim_data.count))
                    dim_count_vars[dim_name] = count_var
                    solver.add(Or(cnt == 0, *[
                        And(i < cnt, var_list[i] == count_var - 1) for i in range(max_n)
                    ]))

        col_pattern = grid.cols.pattern if (grid is not None and grid.cols is not None) else []
        row_pattern = grid.rows.pattern if (grid is not None and grid.rows is not None) else []
        pool_size_overrides = [ref.overrides.get("size", {}) for ref in self.pool]

        def axis_options(pattern, var):
            # every position picks -1..len(pool)-1 from `pattern` (cycled); the referenced
            # pool entry's own explicit size override (only the keys it set) then layers on
            # top of the item's regular size spec for positions matching that value of `var`.
            if not pattern:
                return [(True, {})]
            plen = len(pattern)
            opts = []
            for v in range(max_n):
                target = pattern[v % plen]
                override = pool_size_overrides[target] if 0 <= target < len(self.pool) else {}
                opts.append((var == v, override))
            return opts

        for i in range(max_n):
            active = i < cnt
            solver.add(If(active, And(w[i] >= 1, h[i] >= 1), And(x[i] == 0, y[i] == 0, w[i] == 0, h[i] == 0)))
            solver.add(Implies(active, x[i] >= margin))
            solver.add(Implies(active, y[i] >= margin))
            solver.add(Implies(active, x[i] + w[i] <= self.bw - margin))
            solver.add(Implies(active, y[i] + h[i] <= self.bh - margin))

            col_opts = axis_options(col_pattern, col[i]) if grid is not None else [(True, {})]
            row_opts = axis_options(row_pattern, row[i]) if grid is not None else [(True, {})]

            for idx in range(-1, len(self.pool)):
                base_spec = self.size if idx == -1 else self.pool[idx].size
                for col_cond, col_override in col_opts:
                    for row_cond, row_override in row_opts:
                        merged = base_spec if not (col_override or row_override) else \
                            {**base_spec, **col_override, **row_override}
                        csts = size_constraints(x[i], y[i], w[i], h[i], merged, self.bw, self.bh)
                        if csts:
                            solver.add(Implies(And(active, slot[i] == idx, col_cond, row_cond), And(csts)))

            if grid is None:
                for j in range(i):
                    same_row = y[j] < y[i] + h[i] + gap
                    solver.add(Implies(active, Or(
                        y[j] + h[j] + gap <= y[i],
                        And(same_row, x[j] + w[j] + gap <= x[i]),
                    )))
            else:
                solver.add(If(active,
                    And(row[i] >= 0, col[i] >= 0, level[i] >= 0),
                    And(row[i] == 0, col[i] == 0, level[i] == 0)))
                if i > 0:
                    if grid.primary_dir is not None:
                        dr = KIND_DROW[grid.primary_dir]
                        dc = KIND_DCOL[grid.primary_dir]
                        val_i = row[i] * dr + col[i] * dc
                        val_prev = row[i-1] * dr + col[i-1] * dc
                        solver.add(Implies(active, val_i >= val_prev))
                    lo_dir, hi_dir, step_dir = parse_range(grid.dir or [0, 7])
                    solver.add(If(active,
                        And(kind[i] >= lo_dir, kind[i] <= hi_dir, (kind[i] - lo_dir) % step_dir == 0, parent[i] >= 0, parent[i] < i),
                        And(kind[i] == -1, parent[i] == -1)))
                    if step_dir > 1:
                        solver.add(Implies(active, (kind[i] - lo_dir) % step_dir == 0))
                solver.add(Implies(i < cnt, And([Or(row[i] != row[j], col[i] != col[j]) for j in range(i)])))

                for dim_name, var_list in [("rows", row), ("cols", col), ("levels", level)]:
                    dim_data = getattr(grid, dim_name)
                    if dim_name in dim_count_vars:
                        solver.add(Implies(active, var_list[i] < dim_count_vars[dim_name]))

                for j in range(i):
                    is_parent = parent[i] == j
                    solver.add(Implies(And(active, is_parent), level[i] == level[j] + 1))
                    for k in range(8):
                        solver.add(Implies(And(active, is_parent, kind[i] == k),
                                            And(row[i] == row[j] + KIND_DROW[k], col[i] == col[j] + KIND_DCOL[k])))
                    if j > 0:
                        solver.add(Implies(And(active, is_parent, parent[j] == parent[i]), kind[j] < kind[i]))

                    same_row = row[i] == row[j]
                    same_col = col[i] == col[j]

                    alignment = grid.cell_alignment
                    if alignment.get("top"):
                        solver.add(Implies(And(active, same_row), y[i] == y[j]))
                    if alignment.get("bottom"):
                        solver.add(Implies(And(active, same_row), y[i] + h[i] == y[j] + h[j]))
                    if alignment.get("left"):
                        solver.add(Implies(And(active, same_col), x[i] == x[j]))
                    if alignment.get("right"):
                        solver.add(Implies(And(active, same_col), x[i] + w[i] == x[j] + w[j]))

                    solver.add(Implies(And(active, same_row), If(
                        col[i] > col[j], x[i] >= x[j] + w[j] + gap, x[j] >= x[i] + w[i] + gap)))
                    solver.add(Implies(And(active, same_row),
                        And(y[i] <= y[j] + h[j] - 1, y[j] <= y[i] + h[i] - 1)))
                    if rows_gap_set:
                        solver.add(Implies(And(active, row[i] != row[j]), If(
                            row[i] > row[j], y[i] >= y[j] + h[j] + row_gap, y[j] >= y[i] + h[i] + row_gap)))
                    else:
                        solver.add(Implies(And(active, row[i] != row[j]), If(
                            row[i] > row[j], y[i] >= y[j] + 1 + gap, y[j] >= y[i] + 1 + gap)))

                    solver.add(Implies(And(active, same_col), If(
                        row[i] > row[j], y[i] >= y[j] + h[j] + gap, y[j] >= y[i] + h[i] + gap)))
                    solver.add(Implies(And(active, same_col),
                        And(x[i] <= x[j] + w[j] - 1, x[j] <= x[i] + w[i] - 1)))
                    if cols_gap_set:
                        solver.add(Implies(And(active, col[i] != col[j]), If(
                            col[i] > col[j], x[i] >= x[j] + w[j] + col_gap, x[j] >= x[i] + w[i] + col_gap)))
                    else:
                        solver.add(Implies(And(active, col[i] != col[j]), If(
                            col[i] > col[j], x[i] >= x[j] + 1 + gap, x[j] >= x[i] + 1 + gap)))

                    full_x_ij = x[i] >= x[j] + w[j] + gap
                    full_x_ji = x[j] >= x[i] + w[i] + gap
                    full_y_ij = y[i] >= y[j] + h[j] + gap
                    full_y_ji = y[j] >= y[i] + h[i] + gap

                    solver.add(Implies(And(active, row[i] - row[j] == 1, col[i] - col[j] == 1),
                        Or(full_x_ij, full_y_ij)))
                    solver.add(Implies(And(active, row[i] - row[j] == 1, col[j] - col[i] == 1),
                        Or(full_x_ji, full_y_ij)))
                    solver.add(Implies(And(active, row[j] - row[i] == 1, col[i] - col[j] == 1),
                        Or(full_x_ij, full_y_ji)))
                    solver.add(Implies(And(active, row[j] - row[i] == 1, col[j] - col[i] == 1),
                        Or(full_x_ji, full_y_ji)))

        return result

@dataclass
class GeometryTemplate(BoundedSolver):
    name: str
    type: TypeSpec = "None"
    size: SizeSpec = field(default_factory=dict)
    color: RangeSpec = -1
    edge_color: Optional[RangeSpec] = None
    vertice_color: Optional[RangeSpec] = None
    fill_color: Optional[RangeSpec] = None
    cut: Optional[CutSpec] = None
    geometries: list[GeometryGroup] = field(default_factory=list)

    def generate_child_models(self, width: int, height: int,
                         rng: Optional[random.Random] = None) -> list["ModelRef"]:
        return [g.generate_model(width, height, rng) for g in self.geometries]
    
    def get_prefix(self) -> str:
        return f"tmpl_{self.name}_{id(self)}"

    def add_constraints(self) -> dict:
        if not self.cut:
            return {}
        solver = self.solver
        cuts = {}
        for corner in ("tl", "tr", "br", "bl"):
            v = Int(f"{self.get_prefix()}_cut_{corner}")
            cuts[corner] = v
            spec = self.cut.get(corner, 0)
            solver.add(range_expr(v, spec))
            solver.add(v >= 0)

        solver.add(cuts["tl"] + cuts["tr"] <= self.bw - 1)
        solver.add(cuts["bl"] + cuts["br"] <= self.bw - 1)
        solver.add(cuts["tl"] + cuts["bl"] <= self.bh - 1)
        solver.add(cuts["tr"] + cuts["br"] <= self.bh - 1)

        return cuts

@dataclass
class CanvasFactory:
    root: str
    templates: dict[str, GeometryTemplate]

    def generate_child_models(self, template: str, width: int, height: int,
                         rng: Optional[random.Random] = None) -> list["ModelRef"]:
        return self.templates[template].generate_child_models(width, height, rng)


factory_converter = cattrs.Converter(forbid_extra_keys=True)

def _structure_reference(data: GeometryReferenceSpec, _) -> GeometryReference:
    known = {"template", "tag", "weight", "dir", "origin"}
    overrides = {k: v for k, v in data.items() if k not in known}
    if "geometries" in overrides:
        overrides["geometries"] = [factory_converter.structure(g, GeometryGroup) for g in overrides["geometries"]]
    return GeometryReference(
        template=data.get("template"),
        tag=data.get("tag"),
        dir=data.get("dir"),
        origin=data.get("origin"),
        overrides=overrides,
    )

def _structure_group(data: GeometryGroupSpec, _) -> GeometryGroup:
    fields = set(GeometryGroup.__dataclass_fields__)
    kwargs = {k: v for k, v in data.items() if k in fields}
    kwargs["pool"] = [factory_converter.structure(p, GeometryReference) for p in kwargs.get("pool", [])]
    for axis in ("levels", "rows", "cols"):
        if axis in kwargs:
            val = kwargs[axis]
            if not isinstance(val, dict):
                val = {"count": val}
            kwargs[axis] = factory_converter.structure(val, DimensionData)
    if "grid" in kwargs:
        kwargs["grid"] = factory_converter.structure(kwargs["grid"], GridData)
    return GeometryGroup(**kwargs)

def _structure_template(data: GeometryTemplateSpec, _) -> GeometryTemplate:
    fields = set(GeometryTemplate.__dataclass_fields__) - {"name"}
    kwargs = {k: v for k, v in data.items() if k in fields} if data is not None else {}
    kwargs["geometries"] = [factory_converter.structure(g, GeometryGroup) for g in kwargs.get("geometries", [])]
    return GeometryTemplate(name="", **kwargs)

def _cache_sizes(templates: dict[str, GeometryTemplate], groups: list[GeometryGroup]):
    for group in groups:
        tmpl = templates.get(group.template)
        group.size = tmpl.size if tmpl is not None else {}
        for ref in group.pool:
            resolved_template = ref.template if ref.template is not None else group.template
            rtmpl = templates.get(resolved_template) if resolved_template else None
            ref.size = {**(rtmpl.size if rtmpl is not None else {}), **ref.overrides.get("size", {})}
            if "geometries" in ref.overrides:
                _cache_sizes(templates, ref.overrides["geometries"])

def _structure_factory(data: CanvasFactorySpec, _) -> CanvasFactory:
    templates = {}
    spec_map = data["templates"]
    resolved = {}

    def resolve(name: str) -> dict:
        if name in resolved:
            return resolved[name]
        spec = spec_map[name]
        parent_name = spec.get("template")
        if parent_name:
            temp = resolve(parent_name).copy()
            temp.update(spec)
            spec = temp
        resolved[name] = spec
        return spec

    for name in spec_map:
        resolve(name)

    for name, merged_spec in resolved.items():
        tmpl = factory_converter.structure(merged_spec, GeometryTemplate)
        tmpl.name = name
        templates[name] = tmpl

    for tmpl in templates.values():
        _cache_sizes(templates, tmpl.geometries)

    return CanvasFactory(root=data["root"], templates=templates)

factory_converter.register_structure_hook(RangeSpec, lambda v, t: v)
factory_converter.register_structure_hook(Optional[RangeSpec], lambda v, t: v)
factory_converter.register_structure_hook(GeometryReference, _structure_reference)
factory_converter.register_structure_hook(GeometryGroup, _structure_group)
factory_converter.register_structure_hook(GeometryTemplate, _structure_template)
factory_converter.register_structure_hook(CanvasFactory, _structure_factory)

def build_factory(spec: CanvasFactorySpec) -> CanvasFactory:
    return factory_converter.structure(spec, CanvasFactory)
