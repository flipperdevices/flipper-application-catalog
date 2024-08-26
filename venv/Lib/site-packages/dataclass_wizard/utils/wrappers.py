"""
Wrapper utilities
"""
from typing import Callable


class FuncWrapper:
    """
    Wraps a callable `f` - which is occasionally useful, for example when
    defining functions as :class:`Enum` values. See below answer for more
    details.

    https://stackoverflow.com/a/40339397/10237506
    """
    __slots__ = ('f', )

    def __init__(self, f: Callable):
        self.f = f

    def __call__(self, *args, **kwargs):
        return self.f(*args, **kwargs)
