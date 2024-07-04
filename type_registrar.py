from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, TypeVar, Generic, Iterable, cast, TYPE_CHECKING, Callable


class UnknownType(Exception):
    pass


class Type(ABC):
    TYPE_ID: str


T = TypeVar("T", bound=Type)


class TypeRegistrar(Generic[T]):
    def __init__(
        self,
    ):
        self.types: dict[str, type[T]] = dict()

    def register(self, id: str):
        def registered(cls):
            cls.TYPE_ID = id
            self.types[id] = cls
            return cls

        return registered

    def add_type(self, id: str, type: type[T]):
        self.types[id] = type

    def get_type(self, type_id: str) -> type[T]:
        type = self.types.get(type_id)
        if type:
            return type
        else:
            raise UnknownType(type_id)
