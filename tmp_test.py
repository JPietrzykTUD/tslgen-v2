from abc import ABC, abstractmethod
from tslc.ir.segments import Region, Segment, RawText
from tslc.lower.context import LoweringContext


class AbstractLowerer(ABC):
    @abstractmethod
    @property
    def key(self) -> str:
        pass
    @abstractmethod
    def lower(self, segment: Segment, context: LoweringContext, render: RenderBody) -> str:
        pass

class KeywordLowererRegistry:
    _registry: dict[str, AbstractLowerer] = {}
    @classmethod
    def register_keyword(cls, lowerer: AbstractLowerer):
        if isinstance(lowerer, type):
            instance = lowerer()
            name = lowerer.__name__
        else:
            instance = lowerer
            name = type(lowerer).__name__
        if not isinstance(instance, AbstractLowerer):
            raise TypeError(f"{name} does not fulfil the KeywordLowerer protocol")
        cls._registry[instance.key] = instance
    @classmethod
    def lower(cls, segment: Segment, context: LoweringContext, render: RenderBody) -> str:
        if not isinstance(segment, RawText):
            raise ValueError(f"Segment {segment} is not a RawText, but expected a RawText with keyword in {list(cls._registry.keys())}")
        if segment.keyword not in cls._registry:
            raise ValueError(f"RawText {segment} has keyword {segment.keyword}, but no lowerer is registered for that keyword")
        return cls._registry[segment.keyword].lower(segment, context, render)

@KeywordLowererRegistry.register_keyword
class KeywordBaseInLowerer(AbstractLowerer):
    _KEY: str = "base::in"
    @property
    def key(self) -> str:
        return self._KEY
    def lower(self, segment: Segment, context: LoweringContext, render: RenderBody) -> str:
        return context.type_tag


class RegionLowererRegistry:
    _registry: dict[str, AbstractLowerer] = {}
    @classmethod
    def register_region(cls, lowerer: AbstractLowerer):
        if isinstance(lowerer, type):
            instance = lowerer()
            name = lowerer.__name__
        else:
            instance = lowerer
            name = type(lowerer).__name__
        if not isinstance(instance, AbstractLowerer):
            raise TypeError(f"{name} does not fulfil the AbstractLowerer protocol")
        cls._registry[instance.key] = instance
    @classmethod
    def lower(cls, segment: Segment, context: LoweringContext, render: RenderBody) -> str:
        if not isinstance(segment, Region):
            raise ValueError(f"Segment {segment} is not a Region, but expected a Region with keyword in {list(cls._registry.keys())}")
        if segment.keyword not in cls._registry:
            raise ValueError(f"Region {segment} has keyword {segment.keyword}, but no lowerer is registered for that keyword")
        return cls._registry[segment.keyword].lower(segment, context, render)

@RegionLowererRegistry.register_region
class RegionTypeLowerer:
    _KEY: str = "type"
    _SELECTOR: str = "generation"
    _registry: dict[str, AbstractLowerer] = {}
    @classmethod
    def register_request(cls, lowerer: AbstractLowerer):
        if isinstance(lowerer, type):
            instance = lowerer()
            name = lowerer.__name__
        else:
            instance = lowerer
            name = type(lowerer).__name__
        if not isinstance(instance, AbstractLowerer):
            raise TypeError(f"{name} does not fulfil the AbstractLowerer protocol")
        cls._registry[instance.key] = instance
    def lower(self, segment: Segment, context: LoweringContext, render: RenderBody) -> str:
        if segment.selector_text != self._SELECTOR:
            raise ValueError(f"Region {segment} has selector_text {segment.selector_text}, but expected selector_text {self._SELECTOR} for keyword {self._KEY}")
        for i, subsegment in enumerate(segment.body):
            if isinstance(subsegment, Region) and subsegment.keyword in self._registry:
                segment.body[i] = self._registry[subsegment.keyword].lower(subsegment, context, render)

@RegionTypeLowerer.register_request
class SignedOfRequestLowerer:
    _KEY: str = "base::signed_of"
    @property
    def key(self) -> str:
        return self._KEY
    def lower(self, segment: Segment, context: LoweringContext, render: RenderBody) -> str:
        if len(segment.body) != 1:
            raise ValueError(f"Region {segment} has body of length {len(segment.body)}, but expected body of length 1 for keyword {self._KEY}")
        if segment.selector_text is not None:
            raise ValueError(f"Region {segment} has selector_text {segment.selector_text}, but expected no selector_text for keyword {self._KEY}")
        subsegment = segment.body[0]
        if isinstance(subsegment, RawText):
            type = subsegment.text
        elif isinstance(subsegment, Region) and subsegment.keyword in RegionTypeLowerer._registry:
            type = RegionTypeLowerer._registry[subsegment.keyword].lower(subsegment, context, render)
        else:
            raise ValueError(f"Region {segment} has body with subsegment {subsegment}, but expected a single RawText or a Region with keyword in {list(RegionTypeLowerer._registry.keys())} for keyword {self._KEY}")
        if type.startswith("i") or type.startswith("f"):
            return type
        return "i" + type[1:]
        

# from typing import Callable, Protocol, runtime_checkable
# from enum import IntEnum
# import re
# from tslc.lower.context import LoweringContext
# from tslc.ir.segments import Region, Segment, RawText

# class Phase(IntEnum):
#     STATIC_TRAIT       = 0
#     STATIC_TYPES       = 1
#     STATIC_CONTROL     = 2
#     GENERAL            = 3

# RenderBody = Callable[[tuple[Segment, ...]], str]

    
# @runtime_checkable
# class RegionLowerer(Protocol):
#     def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str: ...


# class LowererPipeline:
#     _pipeline: list[tuple[Phase, RegionLowerer]] = []
#     _initialized = False
#     @classmethod
#     def register(cls, lowerer: type[RegionLowerer] | RegionLowerer | None = None, *, phase: Phase = Phase.GENERAL):
#         cls._initialized = False
#         def _register(l):
#             if isinstance(l, type):
#                 instance = l()
#                 name = l.__name__
#             else:
#                 instance = l
#                 name = type(l).__name__
#             if not isinstance(instance, RegionLowerer):
#                 raise TypeError(f"{name} does not fulfil the RegionLowerer protocol")
#             cls._pipeline.append((phase, instance))
#             return l
#         if lowerer is not None:
#             return _register(lowerer)  # called as @register
#         return _register               # called as @register(phase=...)
#     @classmethod
#     def lower(cls, value: str) -> str:
#         if not cls._initialized:
#             cls._pipeline.sort(key=lambda x: x[0])
#             cls._initialized = True
#         for _, lowerer in cls._pipeline:
#             value = lowerer.lower(value)
#         return value


# @runtime_checkable
# class StaticTypeLowerer(Protocol):
#     @property
#     def key(self) -> str:
#         ...
#     def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> str: ...
    

# class StaticTypeLowererRegistry:
#     _KEY: str = "type"
#     _SELECTOR: str = "generation"
#     _type_registry: dict[str, StaticTypeLowerer] = {}
#     @classmethod
#     def register_type(cls, lowerer: StaticTypeLowerer):
#         if isinstance(lowerer, type):
#             instance = lowerer()
#             name = lowerer.__name__
#         else:
#             instance = lowerer
#             name = type(lowerer).__name__
#         if not isinstance(instance, StaticTypeLowerer):
#             raise TypeError(f"{name} does not fulfil the StaticTypeLowerer protocol")
#         cls._type_registry[instance.key] = instance
#     def lower(self, segment: Segment, context: LoweringContext, render: RenderBody) -> RawText:
#         if not isinstance(segment, Region):
#             raise ValueError(f"Segment {segment} is not a Region, but {self._KEY} regions should be")
#         if segment.keyword != self._KEY:
#             raise ValueError(f"Region {segment} has keyword {segment.keyword}, but {self._KEY} regions should have keyword {self._KEY}")
#         if segment.select_text != self._SELECTOR:
#             raise ValueError(f"Region {segment} has select_text {segment.select_text}, but {self._KEY} regions should have select_text {self._SELECTOR}")
#         if len(segment.body) != 1:
#             raise ValueError(f"Region {segment} has body of length {len(segment.body)}, but {self._KEY} regions should have body of length 1")
#         if isinstance(segment.body[0], RawText):
#             return segment.body[0].text
#         if segment.body[0].keyword not in self._type_registry:
#             raise ValueError(f"Region {segment} has body with keyword {segment.body[0].keyword}, but no lowerer is registered for that keyword")
#         return self._type_registry[segment.body[0].keyword].lower(segment.body[0], context, render)

# @StaticTypeLowerer.register_type
# class TypeBaseInLowerer:
#     _KEY: str = "base::in"
#     @property
#     def key(self) -> str:
#         return self._KEY
#     def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> RawText:
#         if len(region.body) != 0:
#             raise ValueError(f"Region {region} has body of length {len(region.body)}, but {self._KEY} regions should have empty body")
#         if region.selector_text is not None:
#             raise ValueError(f"Region {region} has selector_text {region.selector_text}, but {self._KEY} regions should have no selector_text")
#         return context.type_tag

# class TypeRequestSignedOfLowerer:
#     _KEY: str = "base::signed_of"
#     @property
#     def key(self) -> str:
#         return self._KEY
#     def lower(self, region: Region, context: LoweringContext, render: RenderBody) -> RawText:
#         if len(region.body) != 1:
#             raise ValueError(f"Region {region} has body of length {len(region.body)}, but {self._KEY} regions should have body of length 1")
#         if region.selector_text is not None:
#             raise ValueError(f"Region {region} has selector_text {region.selector_text}, but {self._KEY} regions should have no selector_text")
#         if isinstance(region.body[0], RawText):
#             type = region.body[0].text
        
#         if region.body[0].keyword not in self._type_registry:
#             raise ValueError(f"Region {region} has body with keyword {region.body[0].keyword}, but no lowerer is registered for that keyword")
#         unsigned_type = self._type_registry[region.body[0].keyword].lower(region.body[0], context, render)
#         if unsigned_type.endswith("u"):
#             return unsigned_type[:-1] + "i"
#         raise ValueError(f"Type {unsigned_type} is not an unsigned type, so cannot get signed version")