"""
Re-usable Enum definitions

"""
from enum import Enum

from .utils.string_conv import *
from .utils.wrappers import FuncWrapper


class DateTimeTo(Enum):
    ISO_FORMAT = 0
    TIMESTAMP = 1


class LetterCase(Enum):

    # Converts strings (generally in snake case) to camel case.
    #   ex: `my_field_name` -> `myFieldName`
    CAMEL = FuncWrapper(to_camel_case)
    # Converts strings to "upper" camel case.
    #   ex: `my_field_name` -> `MyFieldName`
    PASCAL = FuncWrapper(to_pascal_case)
    # Converts strings (generally in camel or snake case) to lisp case.
    #   ex: `myFieldName` -> `my-field-name`
    LISP = FuncWrapper(to_lisp_case)
    # Converts strings (generally in camel case) to snake case.
    #   ex: `myFieldName` -> `my_field_name`
    SNAKE = FuncWrapper(to_snake_case)

    def __call__(self, *args):
        return self.value.f(*args)
