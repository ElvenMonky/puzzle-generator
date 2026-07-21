import random
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, TypedDict
import cattrs
from z3 import Int, And, Or, If, Implies, Solver, sat, ModelRef
from size_and_range import RangeSpec, SizeSpec, parse_range, range_expr, size_constraints

KIND_DCOL = {0: 1, 1: 1, 2: 0, 3: -1, 4: -1, 5: -1, 6: 0, 7: 1}
KIND_DROW = {0: 0, 1: 1, 2: 1, 3: 1, 4: 0, 5: -1, 6: -1, 7: -1}

TypeSpec = Literal["None", "Line", "Point", "Polygon"]
LinkOrderSpec = Literal["rng", "bfs", "dfs"]

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
    prefix: list[int]
    pattern: list[int]

class LinkSpec(TypedDict, total=False):
    order: LinkOrderSpec
    dir: RangeSpec
    root_dir: RangeSpec
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
    gap: RangeSpec
    margin: RangeSpec
    link: LinkSpec
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

@dataclass
class DimensionData:
    count: RangeSpec = 1
    prefix: list[int] = field(default_factory=list)
    pattern: list[int] = field(default_factory=list)

@dataclass
class LinkData:
    order: LinkOrderSpec = "rng"
    dir: RangeSpec = 0
    root_dir: RangeSpec = 0
    levels: Optional[DimensionData] = None
    rows: Optional[DimensionData] = None
    cols: Optional[DimensionData] = None
    color: RangeSpec = -1
    above: bool = False

@dataclass
class GeometryGroup:
    template: Optional[str] = None
    tag: Optional[str] = None
    dir: RangeSpec = 0
    origin: OriginSpec = field(default_factory=dict)
    count: RangeSpec = 1
    prefix: list[int] = field(default_factory=list)
    pattern: list[int] = field(default_factory=list)
    gap: RangeSpec = 0
    margin: RangeSpec = 0
    link: Optional[LinkData] = None
    pool: list[GeometryReference] = field(default_factory=list)

    def resolve(self, ref: GeometryReference) -> GeometryReference:
        return GeometryReference(
            template=ref.template if ref.template is not None else self.template,
            tag=ref.tag if ref.tag is not None else self.tag,
            dir=ref.dir if ref.dir is not None else self.dir,
            origin=ref.origin if ref.origin is not None else self.origin,
            overrides=ref.overrides,
        )

    def add_constraints(self, solver, templates: dict[str, "GeometryTemplate"], pw, ph, prefix: str):
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
                solver.add(slot[i] == self.prefix[i])
            elif self.pattern and (i - len(self.prefix)) >= 0:
                solver.add(slot[i] == self.pattern[(i - len(self.prefix)) % len(self.pattern)])
            else:
                solver.add(And(slot[i] >= -1, slot[i] < len(self.pool)))

        result = {"cnt": cnt, "x": x, "y": y, "w": w, "h": h, "slot": slot}

        link = self.link
        if link is not None:
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

        for i in range(max_n):
            active = i < cnt
            solver.add(If(active, And(w[i] >= 1, h[i] >= 1), And(x[i] == 0, y[i] == 0, w[i] == 0, h[i] == 0)))
            solver.add(Implies(active, x[i] >= margin))
            solver.add(Implies(active, y[i] >= margin))
            solver.add(Implies(active, x[i] + w[i] <= pw - margin))
            solver.add(Implies(active, y[i] + h[i] <= ph - margin))

            for idx in range(-1, len(self.pool)):
                tmpl_name = self.template
                overrides = {}
                if idx >= 0:
                    ref = self.resolve(self.pool[idx])
                    if ref.template is not None:
                        tmpl_name = ref.template
                        overrides = ref.overrides.get("size", {})

                base_size = {}
                if tmpl_name is not None and tmpl_name in templates:
                    base_size = templates[tmpl_name].size
                size_spec = {**base_size, **overrides}

                csts = size_constraints(x[i], y[i], w[i], h[i], size_spec, pw, ph)
                if csts:
                    solver.add(Implies(And(active, slot[i] == idx), And(csts)))

            if link is None:
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
                    solver.add(If(active,
                        And(kind[i] >= 0, kind[i] <= 7, parent[i] >= 0, parent[i] < i),
                        And(kind[i] == -1, parent[i] == -1)))
                solver.add(Implies(i < cnt, And([Or(row[i] != row[j], col[i] != col[j]) for j in range(i)])))

                for axis, var in (("rows", row[i]), ("cols", col[i]), ("levels", level[i])):
                    dim = getattr(link, axis)
                    if dim is not None:
                        _, hi, _ = parse_range(dim.count)
                        solver.add(Implies(active, var < hi))

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

                    solver.add(Implies(And(active, same_row), If(
                        col[i] > col[j], x[i] >= x[j] + w[j] + gap, x[j] >= x[i] + w[i] + gap)))
                    solver.add(Implies(And(active, same_row, Or(col[i] - col[j] == 1, col[j] - col[i] == 1)),
                        And(y[i] <= y[j] + h[j] - 1, y[j] <= y[i] + h[i] - 1)))

                    solver.add(Implies(And(active, same_col), If(
                        row[i] > row[j], y[i] >= y[j] + h[j] + gap, y[j] >= y[i] + h[i] + gap)))
                    solver.add(Implies(And(active, same_col, Or(row[i] - row[j] == 1, row[j] - row[i] == 1)),
                        And(x[i] <= x[j] + w[j] - 1, x[j] <= x[i] + w[i] - 1)))

                    x_shift_ij = x[i] - x[j] >= 1 + gap
                    x_shift_ji = x[j] - x[i] >= 1 + gap
                    y_shift_ij = y[i] - y[j] >= 1 + gap
                    y_shift_ji = y[j] - y[i] >= 1 + gap
                    full_x_ij = x[i] >= x[j] + w[j] + gap
                    full_x_ji = x[j] >= x[i] + w[i] + gap
                    full_y_ij = y[i] >= y[j] + h[j] + gap
                    full_y_ji = y[j] >= y[i] + h[i] + gap

                    solver.add(Implies(And(active, row[i] - row[j] == 1, col[i] - col[j] == 1),
                        Or(And(full_x_ij, y_shift_ij), And(full_y_ij, x_shift_ij))))
                    solver.add(Implies(And(active, row[i] - row[j] == 1, col[j] - col[i] == 1),
                        Or(And(full_x_ji, y_shift_ij), And(full_y_ij, x_shift_ji))))
                    solver.add(Implies(And(active, row[j] - row[i] == 1, col[i] - col[j] == 1),
                        Or(And(full_x_ij, y_shift_ji), And(full_y_ji, x_shift_ij))))
                    solver.add(Implies(And(active, row[j] - row[i] == 1, col[j] - col[i] == 1),
                        Or(And(full_x_ji, y_shift_ji), And(full_y_ji, x_shift_ji))))

        return result

@dataclass
class GeometryTemplate:
    name: str
    type: TypeSpec = "None"
    size: SizeSpec = field(default_factory=dict)
    color: RangeSpec = -1
    edge_color: Optional[RangeSpec] = None
    vertice_color: Optional[RangeSpec] = None
    fill_color: Optional[RangeSpec] = None
    cut: CutSpec = field(default_factory=dict)
    geometries: list[GeometryGroup] = field(default_factory=list)

    solver: Optional["Solver"] = field(default=None, init=False, repr=False, compare=False)
    bw: Any = field(default=None, init=False, repr=False, compare=False)
    bh: Any = field(default=None, init=False, repr=False, compare=False)
    group_results: list = field(default=None, init=False, repr=False, compare=False)

    def init_solver(self, templates: dict[str, "GeometryTemplate"]) -> Solver:
        if self.solver is not None:
            return self.solver
        self.bw = Int(f"{self.name}.w")
        self.bh = Int(f"{self.name}.h")
        solver = Solver()
        self.group_results = [
            group.add_constraints(solver, templates, self.bw, self.bh, f"{self.name}.g{i}")
            for i, group in enumerate(self.geometries)
        ]
        self.solver = solver
        return solver

    def generate_model(self, templates: dict[str, "GeometryTemplate"], width: int, height: int,
                        rng: Optional[random.Random] = None) -> ModelRef:
        solver = self.init_solver(templates)
        solver.set("random_seed", (rng or random).randint(0, 2**31 - 1))
        solver.push()
        solver.add(self.bw == width, self.bh == height)
        try:
            if solver.check() != sat:
                raise ValueError(f"{self.name}: unsat for {width}x{height}")
            return solver.model()
        finally:
            solver.pop()

@dataclass
class CanvasFactory:
    root: str
    templates: dict[str, GeometryTemplate]

    def generate_model(self, template: str, width: int, height: int,
                       rng: Optional[random.Random] = None) -> ModelRef:
        return self.templates[template].generate_model(self.templates, width, height, rng)


factory_converter = cattrs.Converter()

def _structure_reference(data: GeometryReferenceSpec, _) -> GeometryReference:
    known = {"template", "tag", "weight", "dir", "origin"}
    overrides = {k: v for k, v in data.items() if k not in known}
    if "geometries" in overrides:
        overrides["geometries"] = [factory_converter.structure(g, GeometryGroup) for g in overrides["geometries"]]
    return GeometryReference(
        template=data.get("template"),
        tag=data.get("tag"),
        weight=data.get("weight"),
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
    if "link" in kwargs:
        kwargs["link"] = factory_converter.structure(kwargs["link"], LinkData)
    return GeometryGroup(**kwargs)

def _structure_template(data: GeometryTemplateSpec, _) -> GeometryTemplate:
    fields = set(GeometryTemplate.__dataclass_fields__) - {"name"}
    kwargs = {k: v for k, v in data.items() if k in fields} if data is not None else {}
    kwargs["geometries"] = [factory_converter.structure(g, GeometryGroup) for g in kwargs.get("geometries", [])]
    return GeometryTemplate(name="", **kwargs)

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

    return CanvasFactory(root=data["root"], templates=templates)

factory_converter.register_structure_hook(int | list[int], lambda v, t: v)
factory_converter.register_structure_hook(GeometryReference, _structure_reference)
factory_converter.register_structure_hook(GeometryGroup, _structure_group)
factory_converter.register_structure_hook(GeometryTemplate, _structure_template)
factory_converter.register_structure_hook(CanvasFactory, _structure_factory)

def build_factory(spec: CanvasFactorySpec) -> CanvasFactory:
    return factory_converter.structure(spec, CanvasFactory)
