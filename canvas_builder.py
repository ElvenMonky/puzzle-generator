import random

from typing import Optional
from canvas import CanvasSpec, GeometrySpec
from canvas_factory import CanvasFactory, CutSpec, GeometryGroup, GeometryReference
from size_and_range import roll_range

def build_vertices(ox: int, oy: int, w: int, h: int, cuts: CutSpec) -> list[tuple[int, int]]:
    tl, tr, br, bl = cuts["tl"], cuts["tr"], cuts["br"], cuts["bl"]
    raw = []
    raw.append((ox + tl, oy))
    raw.append((ox + w - 1 - tr, oy))
    if tr: raw.append((ox + w - 1, oy + tr))
    raw.append((ox + w - 1, oy + h - 1 - br))
    if br: raw.append((ox + w - 1 - br, oy + h - 1))
    raw.append((ox + bl, oy + h - 1))
    if bl: raw.append((ox, oy + h - 1 - bl))
    if tl: raw.append((ox, oy + tl))

    pts = []
    for p in raw:
        if not pts or p != pts[-1]:
            pts.append(p)
    if len(pts) > 1 and pts[-1] == pts[0]:
        pts.pop()
    return pts

def build_group(factory: CanvasFactory, group: GeometryGroup, model, px: int, py: int, rng: random.Random) -> list[GeometrySpec]:
    result = group.result
    items = []
    cnt_val = model[result["cnt"]].as_long()
    grid = group.grid
    col_pattern = grid.cols.pattern if grid is not None and grid.cols is not None else []
    row_pattern = grid.rows.pattern if grid is not None and grid.rows is not None else []
    color_keys = ("color", "edge_color", "vertice_color")

    for i in range(cnt_val):
        x = model[result["x"][i]].as_long()
        y = model[result["y"][i]].as_long()
        w = model[result["w"][i]].as_long()
        h = model[result["h"][i]].as_long()
        slot_val = model[result["slot"][i]].as_long()

        ref: Optional[GeometryReference] = None
        template_name = group.template
        if 0 <= slot_val < len(group.pool):
            ref = group.pool[slot_val]
            template_name = ref.template if ref.template is not None else group.template
        if template_name is None:
            continue

        overrides = dict(ref.overrides) if ref is not None else {}
        if grid is not None:
            col_val = model[result["col"][i]].as_long()
            row_val = model[result["row"][i]].as_long()
            for pattern, val in ((col_pattern, col_val), (row_pattern, row_val)):
                if not pattern:
                    continue
                target = pattern[val % len(pattern)]
                if 0 <= target < len(group.pool):
                    target_overrides = group.pool[target].overrides
                    for key in color_keys:
                        if key in target_overrides:
                            overrides[key] = target_overrides[key]

        ox = w // 2
        oy = h // 2
        if ref is not None and ref.origin is not None:
            if ref.origin.x:
                ox = roll_range(ref.origin.x)
            if ref.origin.y:
                oy = roll_range(ref.origin.y)
        child = build_template_instance(factory, template_name, ox, oy, w, h, rng, overrides=overrides)
        child["x"] = x + ox - px
        child["y"] = y + oy - py
        dir_spec = ref.dir if ref is not None and ref.dir is not None else group.dir
        child["dir"] = roll_range(dir_spec, rng)

        if ref is not None:
            for extra_group in ref.overrides.get("geometries", []):
                extra_model = extra_group.generate_model(w, h, rng)
                child["geometries"].extend(build_group(factory, extra_group, extra_model, ox, oy, rng))

        items.append(child)
    return items

def build_template_instance(factory: CanvasFactory, template_name: str, x: int, y: int, width: int, height: int,
                       rng: random.Random, overrides: Optional[dict] = None) -> GeometrySpec:
    tmpl = factory.templates[template_name]
    overrides = overrides or {}

    geometries = []
    for group in tmpl.geometries:
        model = group.generate_model(width, height, rng)
        geometries.extend(build_group(factory, group, model, x, y, rng))

    color_spec = overrides.get("color", tmpl.color)
    edge_color_spec = overrides.get("edge_color", tmpl.edge_color)
    vertice_color_spec = overrides.get("vertice_color", tmpl.vertice_color)

    color = roll_range(color_spec, rng) if color_spec is not None else None
    edge_color = roll_range(edge_color_spec, rng) if edge_color_spec is not None else None
    vertice_color = roll_range(vertice_color_spec, rng) if vertice_color_spec is not None else None

    vertices = []
    if tmpl.type == "Point":
        vertices = [(0, 0)]
    elif tmpl.type == "Polygon":
        cut_vals: CutSpec = { "tr": 0, "tl": 0, "br": 0, "bl": 0 }
        if tmpl.cut is not None:
            model = tmpl.generate_model(width, height, rng)
            cut_vals = {k: model[v].as_long() for k, v in tmpl.result.items()}
        vertices = build_vertices(-x, -y, width, height, cut_vals)

    return {
        "x": x, "y": y, "dir": 0,
        "vertices": vertices,
        "color": color,
        "edge_color": edge_color,
        "vertice_color": vertice_color,
        "geometries": geometries,
    }

def build_canvas_spec(factory: CanvasFactory, rng: Optional[random.Random] = None) -> CanvasSpec:
    rng = rng or random.Random()
    root_size = factory.templates[factory.root].size
    width = roll_range(root_size.get("width", 1), rng)
    height = roll_range(root_size.get("height", 1), rng)
    root_geom = build_template_instance(factory, factory.root, width // 2, height // 2, width, height, rng)
    return {"width": width, "height": height, "geometries": [root_geom]}
