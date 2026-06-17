class ARCFeature:
    REGISTRY = {}
    props: list[str] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.REGISTRY[cls.__name__] = cls

class Point(ARCFeature):
    props = ["x", "y", "color"]

class Line(ARCFeature):
    props = ["width", "direction", "start", "color"]

class Object(ARCFeature):
    props = ["width", "height", "x", "y", "mask", "color"]

class Glyph(ARCFeature):
    props = ["x", "y", "mask", "color"]

MAX_FEATURES = 12
