import random
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, TypedDict, Union
import cattrs
from z3 import Int, And, Or, If, Implies, Solver, sat, ModelRef
from size_and_range import RangeSpec, SizeSpec, parse_range, range_expr, size_constraints

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

class LinkSpec(TypedDict, total=False):
    order: LinkOrderSpec
    dir: RangeSpec
    root_dir: RangeSpec
    color: RangeSpec
    above: bool

class GeometryTemplateSpec(TypedDict, total=False):
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
    weight: RangeSpec
    dir: RangeSpec
    origin: OriginSpec

class DimensionSpec(TypedDict, total=False):
    count: RangeSpec
    prefix: list[int]
    pattern: list[int]

class GeometryGroupSpec(DimensionSpec, GeometryReferenceSpec, total=False):
    gap: RangeSpec
    margin: RangeSpec
    levels: DimensionSpec
    rows: DimensionSpec
    cols: DimensionSpec
    link: LinkSpec
    pool: list[GeometryReferenceSpec]

class CanvasFactorySpec(TypedDict):
    root: str
    templates: dict[str, GeometryTemplateSpec]

@dataclass
class GeometryReference:
    template: Optional[str] = None
    tag: Optional[str] = None
    weight: Optional[RangeSpec] = None
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
    color: RangeSpec = -1
    above: bool = False

@dataclass
class GeometryGroup:
    template: Optional[str] = None
    tag: Optional[str] = None
    weight: RangeSpec = 1
    dir: RangeSpec = 0
    origin: OriginSpec = field(default_factory=dict)
    count: RangeSpec = 1
    prefix: list[int] = field(default_factory=list)
    pattern: list[int] = field(default_factory=list)
    gap: RangeSpec = 0
    margin: RangeSpec = 0
    levels: Optional[DimensionData] = None
    rows: Optional[DimensionData] = None
    cols: Optional[DimensionData] = None
    link: Optional[LinkData] = None
    pool: list[GeometryReference] = field(default_factory=list)

    def resolve(self, ref: GeometryReference) -> GeometryReference:
        return GeometryReference(
            template=ref.template if ref.template is not None else self.template,
            tag=ref.tag if ref.tag is not None else self.tag,
            weight=ref.weight if ref.weight is not None else self.weight,
            dir=ref.dir if ref.dir is not None else self.dir,
            origin=ref.origin if ref.origin is not None else self.origin,
            overrides=ref.overrides,
        )

    def pick_slot(self) -> GeometryReference:
        own_weight = self.weight if self.template is not None else 0
        total = own_weight + sum((r.weight or 0) for r in self.pool)
        r = random.uniform(0, total)
        for ref in self.pool:
            w = ref.weight or 0
            if r < w:
                return self.resolve(ref)
            r -= w
        return self.resolve(GeometryReference())

    def add_random(self, solver, templates: dict[str, "GeometryTemplate"], pw, ph, prefix: str):
        _, max_n, _ = parse_range(self.count)
        cnt = Int(f"{prefix}.cnt")
        solver.add(range_expr(cnt, self.count))
        gap = Int(f"{prefix}.gap"); solver.add(range_expr(gap, self.gap))
        margin = Int(f"{prefix}.margin"); solver.add(range_expr(margin, self.margin))

        x = [Int(f"{prefix}[{i}].x") for i in range(max_n)]
        y = [Int(f"{prefix}[{i}].y") for i in range(max_n)]
        w = [Int(f"{prefix}[{i}].w") for i in range(max_n)]
        h = [Int(f"{prefix}[{i}].h") for i in range(max_n)]
        slots = [self.pick_slot() for _ in range(max_n)]

        for i in range(max_n):
            active = i < cnt
            solver.add(If(active, And(w[i] >= 1, h[i] >= 1), And(x[i] == 0, y[i] == 0, w[i] == 0, h[i] == 0)))
            solver.add(Implies(active, x[i] >= margin))
            solver.add(Implies(active, y[i] >= margin))
            solver.add(Implies(active, x[i] + w[i] <= pw - margin))
            solver.add(Implies(active, y[i] + h[i] <= ph - margin))
            tmpl = templates[slots[i].template]
            size = {**tmpl.size, **slots[i].overrides.get("size", {})}
            for c in size_constraints(x[i], y[i], w[i], h[i], size, pw, ph):
                solver.add(Implies(active, c))

            for j in range(i):
                same_row = y[j] < y[i] + h[i] + gap
                solver.add(Implies(active, Or(
                    y[j] + h[j] + gap <= y[i],
                    And(same_row, x[j] + w[j] + gap <= x[i]),
                )))

        return cnt, x, y, w, h, slots

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

    def init_solver(self, templates: dict[str, "GeometryTemplate"]) -> "Solver":
        if self.solver is not None:
            return self.solver
        self.bw = Int(f"{self.name}.w")
        self.bh = Int(f"{self.name}.h")
        solver = Solver()
        self.group_results = [
            g.add_random(solver, templates, self.bw, self.bh, f"{self.name}.g{i}")
            for i, g in enumerate(self.geometries)
        ]
        self.solver = solver
        return solver

    def generate_model(self, templates: dict[str, "GeometryTemplate"], width: int, height: int,
                        rng: Optional[random.Random] = None) -> "ModelRef":
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
                        rng: Optional[random.Random] = None) -> "ModelRef":
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
            kwargs[axis] = factory_converter.structure(kwargs[axis], DimensionData)
    if "link" in kwargs:
        kwargs["link"] = factory_converter.structure(kwargs["link"], LinkData)
    return GeometryGroup(**kwargs)

def _structure_template(data: GeometryTemplateSpec, _) -> GeometryTemplate:
    fields = set(GeometryTemplate.__dataclass_fields__) - {"name"}
    kwargs = {k: v for k, v in data.items() if k in fields}
    kwargs["geometries"] = [factory_converter.structure(g, GeometryGroup) for g in kwargs.get("geometries", [])]
    return GeometryTemplate(name="", **kwargs)

def _structure_factory(data: CanvasFactorySpec, _) -> CanvasFactory:
    templates = {}
    for name, spec in data["templates"].items():
        tmpl = factory_converter.structure(spec, GeometryTemplate)
        tmpl.name = name
        templates[name] = tmpl
    return CanvasFactory(root=data["root"], templates=templates)

factory_converter.register_structure_hook(GeometryReference, _structure_reference)
factory_converter.register_structure_hook(GeometryGroup, _structure_group)
factory_converter.register_structure_hook(GeometryTemplate, _structure_template)
factory_converter.register_structure_hook(CanvasFactory, _structure_factory)

def build_factory(spec: CanvasFactorySpec) -> CanvasFactory:
    return factory_converter.structure(spec, CanvasFactory)
