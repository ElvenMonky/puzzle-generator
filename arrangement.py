import random
from dataclasses import dataclass, field
from typing import Literal, Optional

Point = tuple[int, int]

def in_bounds(p: Point, size: Point) -> bool:
    w, h = size
    return 0 <= p[0] < w and 0 <= p[1] < h

DX = [1, 1, 0, -1, -1, -1, 0, 1]
DY = [0, 1, 1, 1, 0, -1, -1, -1]

TurnMode = Literal["next", "random"]
CollisionMode = Literal["stop", "skip"]
RaySelection = Literal["same", "next", "random"]

@dataclass
class Arrangement:
    size: tuple[int, int]
    origin: Optional[Point] = None
    count: Optional[int] = None

    def generate(self) -> list[Point]:
        raise NotImplementedError

@dataclass
class _Ray:
    direction: int
    interval: int
    pos: Point
    turn_idx: int = 0
    steps_left: int = field(init=False)
    tail: set = field(default_factory=set)
    active: bool = True

    def __post_init__(self):
        self.steps_left = self.interval
        self.tail.add(self.pos)

class _RaySelector:
    def __init__(self, mode: RaySelection, rng: random.Random):
        self.mode = mode
        self.rng = rng
        self.idx = 0

    def pick(self, rays: list[_Ray]) -> _Ray:
        if self.mode == "random":
            return self.rng.choice(rays)
        self.idx %= len(rays)
        ray = rays[self.idx]
        if self.mode == "next":
            self.idx += 1
        return ray

@dataclass
class RadialArrangement(Arrangement):
    ray_starts: list[tuple[int, int]] = field(default_factory=list)
    turn_prefix: list[int] = field(default_factory=list)
    turn_pattern: list[int] = field(default_factory=list)
    growth_prefix: list[int] = field(default_factory=list)
    growth_pattern: list[int] = field(default_factory=list)
    fork_prefix: list[int] = field(default_factory=list)
    fork_pattern: list[int] = field(default_factory=list)
    ray_selection: RaySelection = "next"
    turn_mode: TurnMode = "next"
    collision_mode: CollisionMode = "stop"
    seed: Optional[int] = None

    def _turn(self, idx: int, rng: random.Random) -> int:
        if idx < len(self.turn_prefix):
            return self.turn_prefix[idx]
        if not self.turn_pattern:
            return 0
        if self.turn_mode == "random":
            return rng.choice(self.turn_pattern)
        return self.turn_pattern[(idx - len(self.turn_prefix)) % len(self.turn_pattern)]

    def _growth(self, idx: int) -> int:
        if idx < len(self.growth_prefix):
            return self.growth_prefix[idx]
        if not self.growth_pattern:
            return 0
        return self.growth_pattern[(idx - len(self.growth_prefix)) % len(self.growth_pattern)]

    def _fork(self, idx: int) -> int:
        if idx < len(self.fork_prefix):
            return self.fork_prefix[idx]
        if not self.fork_pattern:
            return -1
        return self.fork_pattern[(idx - len(self.fork_prefix)) % len(self.fork_pattern)]

    def _exhausted(self, idx: int) -> bool:
        return (
            not self.turn_pattern and not self.growth_pattern and not self.fork_pattern
            and idx >= len(self.turn_prefix)
            and idx >= len(self.growth_prefix)
            and idx >= len(self.fork_prefix)
        )

    def _advance(self, ray: _Ray, rng: random.Random) -> Optional[_Ray]:
        fork_interval = self._fork(ray.turn_idx)
        forked = _Ray(direction=ray.direction, interval=fork_interval, pos=ray.pos) if fork_interval >= 0 else None
        ray.direction = (ray.direction + self._turn(ray.turn_idx, rng)) % 8
        ray.interval += self._growth(ray.turn_idx)
        ray.turn_idx += 1
        ray.steps_left = float("inf") if self._exhausted(ray.turn_idx) else ray.interval
        return forked

    def generate(self) -> list[Point]:
        rng = random.Random(self.seed)
        rays = [_Ray(direction=d, interval=i, pos=self.origin) for d, i in self.ray_starts]
        selector = _RaySelector(self.ray_selection, rng)
        occupied = {self.origin}
        cells = [self.origin]

        while rays and (self.count is None or len(cells) < self.count):
            ray = selector.pick(rays)
            if ray.steps_left <= 0:
                forked = self._advance(ray, rng)
                if forked is not None:
                    rays.append(forked)
            nxt = (ray.pos[0] + DX[ray.direction], ray.pos[1] + DY[ray.direction])

            if self.collision_mode == "stop":
                blocked = not in_bounds(nxt, self.size) or nxt in occupied
            else:
                blocked = not in_bounds(nxt, self.size) or nxt in ray.tail or nxt == self.origin

            if blocked:
                rays.remove(ray)
                continue

            ray.pos = nxt
            ray.tail.add(nxt)
            if nxt not in occupied:
                occupied.add(nxt)
                cells.append(nxt)

            ray.steps_left -= 1

        return cells
