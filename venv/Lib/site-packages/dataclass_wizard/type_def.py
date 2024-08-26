__all__ = [
    'PyForwardRef',
    'PyLiteral',
    'PyProtocol',
    'PyDeque',
    'PyTypedDict',
    'PyTypedDicts',
    'FrozenKeys',
    'DefFactory',
    'NoneType',
    'ExplicitNullType',
    'ExplicitNull',
    'JSONList',
    'JSONObject',
    'ListOfJSONObject',
    'JSONValue',
    'Encoder',
    'FileEncoder',
    'Decoder',
    'FileDecoder',
    'NUMBERS',
    'T',
    'E',
    'U',
    'M',
    'NT',
    'DT',
    'DD',
    'N',
    'S',
    'LT',
    'LSQ',
    'FREF',
]

from collections import deque
from datetime import date, time, datetime
from enum import Enum
from typing import (
    Any, Type, TypeVar, Sequence, Mapping, List, Dict, DefaultDict, FrozenSet,
    Union, NamedTuple, Callable, AnyStr, TextIO, BinaryIO
)
from uuid import UUID

from .constants import PY36, PY38_OR_ABOVE
from .decorators import discard_kwargs


# Type check for numeric types - needed because `bool` is technically
# a Number.
NUMBERS = int, float

# Generic type
T = TypeVar('T')

# Enum subclass type
E = TypeVar('E', bound=Enum)

# UUID subclass type
U = TypeVar('U', bound=UUID)

# Mapping type
M = TypeVar('M', bound=Mapping)

# NamedTuple type
NT = TypeVar('NT', bound=NamedTuple)

# Date, time, or datetime type
DT = TypeVar('DT', date, time, datetime)

# DefaultDict type
DD = TypeVar('DD', bound=DefaultDict)

# Numeric type
N = TypeVar('N', int, float, complex)

# Sequence type
S = TypeVar('S', bound=Sequence)

# List or Tuple type
LT = TypeVar('LT', list, tuple)

# List, Set, or Deque (Double ended queue) type
LSQ = TypeVar('LSQ', list, set, frozenset, deque)

# A fixed set of key names
FrozenKeys = FrozenSet[str]

# Default factory type, assuming a no-args constructor
DefFactory = Callable[[], T]

# The class of the `None` singleton, cached for re-usability
NoneType = type(None)

# For Python 3.8+, we need to use both `TypedDict` implementations (from both
# the `typing` and `typing_extensions` modules). Because it's not clear which
# version users might choose to use. And they might choose to use either, due
# to the issues mentioned below (comment taken from `typing_extensions`):
#
#   The standard library TypedDict in Python 3.8 does not store runtime information
#   about which (if any) keys are optional.  See https://bugs.python.org/issue38834
#   The standard library TypedDict in Python 3.9.0/1 does not honour the "total"
#   keyword with old-style TypedDict().  See https://bugs.python.org/issue42059
PyTypedDicts: List[Type['TypedDict']] = []

# Valid collection types in JSON.
JSONList = List[Any]
JSONObject = Dict[str, Any]
ListOfJSONObject = List[JSONObject]

# Valid value types in JSON.
JSONValue = Union[None, str, bool, int, float, JSONList, JSONObject]


if PY38_OR_ABOVE:  # pragma: no cover
    from typing import ForwardRef as PyForwardRef
    from typing import Literal as PyLiteral
    from typing import Protocol as PyProtocol
    from typing import TypedDict as PyTypedDict
    from typing import Deque as PyDeque

    PyTypedDicts.append(PyTypedDict)
    # Python 3.8+ users might import from either `typing` or
    # `typing_extensions`, so check for both types.
    try:
        # noinspection PyUnresolvedReferences
        from typing_extensions import TypedDict as PyTypedDict
        PyTypedDicts.append(PyTypedDict)
    except ImportError:
        pass
else:  # pragma: no cover
    from typing_extensions import Literal as PyLiteral
    from typing_extensions import Protocol as PyProtocol
    from typing_extensions import TypedDict as PyTypedDict
    # Seems like `Deque` was only introduced to `typing` in 3.6.1, so Python
    # 3.6.0 won't have it; to be safe, we'll instead import from the
    # `typing_extensions` module here.
    from typing_extensions import Deque as PyDeque

    PyTypedDicts.append(PyTypedDict)

    if PY36:
        import typing
        from typing import _ForwardRef as PyForwardRef
        from functools import wraps

        # Need to wrap the constructor to discard arguments like `is_argument`
        PyForwardRef.__init__ = discard_kwargs(PyForwardRef.__init__)

        # This is needed to avoid an`AttributeError` when using PyForwardRef
        # as an argument to `TypeVar`, as we do below.
        #
        # See https://stackoverflow.com/a/69436981/10237506.
        _old_type_check = typing._type_check

        @wraps(_old_type_check)
        def _new_type_check(arg, message):
            if arg is PyForwardRef:
                return arg
            return _old_type_check(arg, message)

        typing._type_check = _new_type_check
        # ensure the global namespace is the same for users
        # regardless of the version of Python they're using
        del _new_type_check, typing, wraps

    else:
        from typing import ForwardRef as PyForwardRef


# Forward references can be either strings or explicit `ForwardRef` objects.
# noinspection SpellCheckingInspection
FREF = TypeVar('FREF', str, PyForwardRef)


# Create our own "nullish" type for explicit type assertions
class ExplicitNullType:
    __slots__ = ()

    def __bool__(self):
        return False

    def __repr__(self):
        return self.__class__.__qualname__


ExplicitNull = ExplicitNullType()


class Encoder(PyProtocol):
    """
    Represents an encoder for Python object -> JSON, e.g. analogous to
    `json.dumps`
    """

    def __call__(self, obj: Union[JSONObject, JSONList],
                 **kwargs) -> AnyStr:
        ...


class FileEncoder(PyProtocol):
    """
    Represents an encoder for Python object -> JSON file, e.g. analogous to
    `json.dump`
    """

    def __call__(self, obj: Union[JSONObject, JSONList],
                 file: Union[TextIO, BinaryIO],
                 **kwargs) -> AnyStr:
        ...


class Decoder(PyProtocol):
    """
    Represents a decoder for JSON -> Python object, e.g. analogous to
    `json.loads`
    """

    def __call__(self, s: AnyStr,
                 **kwargs) -> Union[JSONObject, ListOfJSONObject]:
        ...


class FileDecoder(PyProtocol):
    """
    Represents a decoder for JSON file -> Python object, e.g. analogous to
    `json.load`
    """
    def __call__(self, file: Union[TextIO, BinaryIO],
                 **kwargs) -> Union[JSONObject, ListOfJSONObject]:
        ...
