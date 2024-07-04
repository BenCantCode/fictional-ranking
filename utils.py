from typing import Callable, Any, TypeVar


def copying_cache(method: Callable[[Any], list[Any]]):
    cache: list[Any] | None = None

    def wrapper(self):
        nonlocal cache
        if cache is not None:
            return cache.copy()
        else:
            cache = method(self)
            return cache.copy()

    return wrapper
