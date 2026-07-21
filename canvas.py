from dataclasses import dataclass, field
from typing import Optional, TypedDict

import cattrs
import numpy as np

PointsSpec = list[tuple[int, int]]
ColoredPointsSpec = list[tuple[int, int, Optional[int]]]

class GeometrySpec(TypedDict):
    x: int
    y: int
    dir: int
    vertices: PointsSpec
    color: Optional[int]
    edge_color: Optional[int]
    vertice_color: Optional[int]
    geometries: list["GeometrySpec"]

class CanvasSpec(TypedDict):
    width: int
    height: int
    geometries: list[GeometrySpec]

def _rotate45(x: int, y: int) -> tuple[int, int]:
    flip = y < 0 or (y == 0 and x < 0)
    if flip:
        x, y = -x, -y
    m = ((1, 0), (1, 1))
    if y <= x:
        m = ((1, -1), (1, 0))
    elif x >= 0:
        m = ((1, -1), (0, 1))
    elif y >= -x:
        m = ((0, -1), (1, 1))
    rx = m[0][0] * x + m[0][1] * y
    ry = m[1][0] * x + m[1][1] * y
    return (-rx, -ry) if flip else (rx, ry)

def _point_in_polygon(px: int, py: int, vertices: PointsSpec) -> bool:
    inside = False
    for i in range(len(vertices)):
        x0, y0 = vertices[i]
        x1, y1 = vertices[i - 1]
        if (y0 > py) != (y1 > py):
            x_edge = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
            if px < x_edge:
                inside = not inside
    return inside

@dataclass
class Geometry:
    x: int = 0
    y: int = 0
    dir: int = 0
    color: Optional[int] = None
    edge_color: Optional[int] = None
    vertice_color: Optional[int] = None
    vertices: PointsSpec = field(default_factory=list)
    geometries: list["Geometry"] = field(default_factory=list)

    def transform(self, x: int, y: int, c: Optional[int]) -> tuple[int, int, Optional[int]]:
        d = self.dir
        x, y = [(x, y), (-y, x), (-x, -y), (y, -x), (x, -y), (y, x), (-x, y), (-y, -x)][d // 2]
        if d % 2 == 1:
            x, y = _rotate45(x, y)
        return x + self.x, y + self.y, c

    def render_own_geometry(self, inherited_color: Optional[int] = None) -> ColoredPointsSpec:
        if not self.vertices:
            return []
        points: dict[int, dict[int, int]] = {}
        xs, ys = [v[0] for v in self.vertices], [v[1] for v in self.vertices]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        color = self.color if self.color is not None else inherited_color
        for py in range(min_y, max_y + 1):
            points[py] = {}
            for px in range(min_x, max_x + 1):
                if _point_in_polygon(px, py, self.vertices):
                    points[py][px] = color
        if self.edge_color is not None:
            color = self.edge_color
        for i in range(len(self.vertices)):
            x0, y0 = self.vertices[i]
            x1, y1 = self.vertices[i - 1]
            if x0 == x1:
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    points[y][x0] = color
            elif y0 == y1:
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    points[y0][x] = color
            elif abs(x1 - x0) == abs(y1 - y0):
                steps = abs(x1 - x0)
                sx = 1 if x1 > x0 else -1
                sy = 1 if y1 > y0 else -1
                for s in range(steps + 1):
                    points[y0 + s * sy][x0 + s * sx] = color
        if self.vertice_color is not None:
            color = self.vertice_color
        for vx, vy in self.vertices:
            points[vy][vx] = color
        return [(x, y, points[y][x]) for y in points for x in points[y]]

    def render(self, inherited_color: Optional[int] = None) -> ColoredPointsSpec:
        color = self.color if self.color is not None else inherited_color

        points = self.render_own_geometry(inherited_color)
        for child in self.geometries:
            points.extend(child.render(color))
        
        return [self.transform(*p) for p in points]

@dataclass
class Canvas:
    width: int
    height: int
    background: int = 0
    layers: list[Geometry] = field(default_factory=list)

    def render(self) -> np.ndarray:
        grid = np.full((self.height, self.width), self.background, dtype=int)

        for layer in self.layers:
            for wx, wy, c in layer.render():
                if 0 <= wx < self.width and 0 <= wy < self.height and c not in (None, -1):
                    grid[wy, wx] = c
        return grid

converter = cattrs.Converter()

def _structure_geometry(data: GeometrySpec, _) -> Geometry:
    fields = set(Geometry.__dataclass_fields__)
    kwargs = {k: v for k, v in data.items() if k in fields}
    if "geometries" in kwargs:
        kwargs["geometries"] = [converter.structure(g, Geometry) for g in kwargs["geometries"]]
    if "vertices" in kwargs:
        kwargs["vertices"] = [tuple(v) for v in kwargs["vertices"]]
    return Geometry(**kwargs)

def _structure_canvas(data: CanvasSpec, _) -> Canvas:
    return Canvas(
        width=data["width"],
        height=data["height"],
        background=data.get("background", 0),
        layers=[converter.structure(g, Geometry) for g in data.get("geometries", [])],
    )

converter.register_structure_hook(Geometry, _structure_geometry)
converter.register_structure_hook(Canvas, _structure_canvas)

def build_canvas(spec: CanvasSpec) -> Canvas:
    return converter.structure(spec, Canvas)
