from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Iterable, cast, TYPE_CHECKING


class UnknownType(Exception):
    pass


class Type(ABC):
    TYPE_ID: str

    if not TYPE_CHECKING:
        # Hack to force TYPE_ID to be overridden
        @property
        @abstractmethod
        def TYPE_ID(self) -> str:
            raise NotImplementedError()


T = TypeVar("T", bound=Type)


class TypeRegistrar(Generic[T]):
    # Hack to force TYPE to be overridden

    DEFAULT_TYPES: list[type[T]] = []

    def __init__(
        self,
        types: list[type[T]] = [],
        include_default: bool = True,
    ):
        if include_default:
            types.extend(self.DEFAULT_TYPES)
        self.types = dict((type.TYPE_ID, type) for type in types)

    def add_type(self, type: type[T]):
        self.types[type.TYPE_ID] = type

    def add_types(self, types: Iterable[type[T]]):
        for type in types:
            self.add_type(type)

    def get_type(self, type_id: str) -> type[T]:
        type = self.types.get(type_id)
        if type:
            return type
        else:
            raise UnknownType(type_id)
