class ARCCriteria:
    REGISTRY = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.REGISTRY[cls.__name__] = cls

class PositionCriteria(ARCCriteria):
    pass

class SizeCriteria(ARCCriteria):
    pass

class MaskCriteria(ARCCriteria):
    pass

class ColorCriteria(ARCCriteria):
    pass

class CompositeCriteria(ARCCriteria):
    pass
