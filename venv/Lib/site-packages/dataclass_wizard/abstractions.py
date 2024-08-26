"""
Contains implementations for Abstract Base Classes
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, InitVar
from datetime import datetime, time, date, timedelta
from decimal import Decimal
from typing import (
    Any, Type, TypeVar, Union, List, Tuple, Dict, SupportsFloat, AnyStr,
    Text, Sequence, Iterable
)

from .models import Extras
from .type_def import (
    DefFactory, FrozenKeys, ListOfJSONObject, JSONObject, Encoder,
    M, N, T, NT, E, U, DD, LSQ
)


# Create a generic variable that can be 'AbstractJSONWizard', or any subclass.
W = TypeVar('W', bound='AbstractJSONWizard')

FieldToParser = Dict[str, 'AbstractParser']


class AbstractJSONWizard(ABC):
    """
    Abstract class that defines the methods a sub-class must implement at a
    minimum to be considered a "true" JSON Wizard.

    In particular, these are the abstract methods which - if correctly
    implemented - will allow a concrete sub-class (ideally a dataclass) to
    be properly loaded from, and serialized to, JSON.

    """
    __slots__ = ()

    @classmethod
    @abstractmethod
    def from_json(cls: Type[W], string: AnyStr) -> Union[W, List[W]]:
        """
        Converts a JSON `string` to an instance of the dataclass, or a list of
        the dataclass instances.
        """

    @classmethod
    @abstractmethod
    def from_list(cls: Type[W], o: ListOfJSONObject) -> List[W]:
        """
        Converts a Python `list` object to a list of the dataclass instances.
        """

    @classmethod
    @abstractmethod
    def from_dict(cls: Type[W], o: JSONObject) -> W:
        """
        Converts a Python `dict` object to an instance of the dataclass.
        """

    @abstractmethod
    def to_dict(self: W) -> JSONObject:
        """
        Converts the dataclass instance to a Python dictionary object that is
        JSON serializable.
        """

    @abstractmethod
    def to_json(self: W, *,
                encoder: Encoder = json.dumps,
                indent=None,
                **encoder_kwargs) -> AnyStr:
        """
        Converts the dataclass instance to a JSON `string` representation.
        """

    @classmethod
    @abstractmethod
    def list_to_json(cls: Type[W],
                     instances: List[W],
                     encoder: Encoder = json.dumps,
                     indent=None,
                     **encoder_kwargs) -> AnyStr:
        """
        Converts a ``list`` of dataclass instances to a JSON `string`
        representation.
        """


@dataclass
class AbstractParser(ABC):
    """
    Abstract parsers, which will ideally act as dispatchers to route objects
    to the `load` or `dump` hook methods responsible for transforming the
    objects into the annotated type for the dataclass field for which value we
    want to set. The error handling logic should ideally be implemented on the
    Parser (dispatcher) side.

    There can be more complex Parsers, for example ones which will handle
    ``typing.Union``, ``typing.Literal``, ``Dict``, and ``NamedTuple`` types.
    There can even be nested Parsers, which will be useful for handling
    collection and sequence types.

    """
    __slots__ = ('base_type', )

    # This represents the class that contains the field that has an annotated
    # type `base_type`. This is primarily useful for resolving `ForwardRef`
    # types, where we need the globals of the class to resolve the underlying
    # type of the reference.
    cls: InitVar[Type]

    # This represents an optional Meta config that was specified for the main
    # dataclass. This is primarily useful to have so that we can merge this
    # base Meta config with the one for each class, and then recursively
    # apply the merged Meta config to any nested dataclasses.
    extras: InitVar[Extras]

    # This is usually the underlying base type of the annotation (for example,
    # for `List[str]` it will be `list`), though in some cases this will be
    # the annotation itself.
    base_type: Type[T]

    def __contains__(self, item) -> bool:
        """
        Return true if the Parser is expected to handle the specified item
        type. Checks against the exact type instead of `isinstance` so we can
        handle special cases like `bool`, which is a subclass of `int`.
        """
        return type(item) is self.base_type

    @abstractmethod
    def __call__(self, o: Any):
        """
        Parse object `o`
        """


class AbstractLoader(ABC):
    """
    Abstract loader which defines the helper methods that can be used to load
    an object `o` into an object of annotated (or concrete) type `base_type`.

    """
    __slots__ = ()

    @staticmethod
    @abstractmethod
    def transform_json_field(string: str) -> str:
        """
        Transform a JSON field name (which will typically be camel-cased) into
        the conventional format for a dataclass field name (which will ideally
        be snake-cased).
        """

    @staticmethod
    @abstractmethod
    def default_load_to(o: T, _: Any) -> T:
        """
        Default load function if no other paths match. Generally, this will
        be a stub load method.
        """

    @staticmethod
    @abstractmethod
    def load_after_type_check(o: Any, base_type: Type[T]) -> T:
        """
        Load an object `o`, after confirming that it is indeed of
        type `base_type`.

        :raises ParseError: If the object is not of the expected type.
        """

    @staticmethod
    @abstractmethod
    def load_to_str(o: Union[Text, N, None], base_type: Type[str]) -> str:
        """
        Load a string or numeric type into a new object of type `base_type`
        (generally a sub-class of the :class:`str` type)
        """

    @staticmethod
    @abstractmethod
    def load_to_int(o: Union[str, int, bool, None], base_type: Type[N]) -> N:
        """
        Load a string or int into a new object of type `base_type`
        (generally a sub-class of the :class:`int` type)
        """

    @staticmethod
    @abstractmethod
    def load_to_float(o: Union[SupportsFloat, str], base_type: Type[N]) -> N:
        """
        Load a string or float into a new object of type `base_type`
        (generally a sub-class of the :class:`float` type)
        """

    @staticmethod
    @abstractmethod
    def load_to_bool(o: Union[str, bool, N], _: Type[bool]) -> bool:
        """
        Load a bool, string, or an numeric value into a new object of type
        `bool`.

        *Note*: `bool` cannot be sub-classed, so the `base_type` argument is
        discarded in this case.
        """

    @staticmethod
    @abstractmethod
    def load_to_enum(o: Union[AnyStr, N], base_type: Type[E]) -> E:
        """
        Load an object `o` into a new object of type `base_type` (generally a
        sub-class of the :class:`Enum` type)
        """

    @staticmethod
    @abstractmethod
    def load_to_uuid(o: Union[AnyStr, U], base_type: Type[U]) -> U:
        """
        Load an object `o` into a new object of type `base_type` (generally a
        sub-class of the :class:`UUID` type)
        """

    @staticmethod
    @abstractmethod
    def load_to_iterable(
            o: Iterable, base_type: Type[LSQ],
            elem_parser: AbstractParser) -> LSQ:
        """
        Load a list, set, frozenset or deque into a new object of type
        `base_type` (generally a list, set, frozenset, deque, or a sub-class
        of one)
        """

    @staticmethod
    @abstractmethod
    def load_to_tuple(
            o: Union[List, Tuple], base_type: Type[Tuple],
            elem_parsers: Sequence[AbstractParser]) -> Tuple:
        """
        Load a list or tuple into a new object of type `base_type` (generally
        a :class:`tuple` or a sub-class of one)
        """

    @staticmethod
    @abstractmethod
    def load_to_named_tuple(
            o: Union[Dict, List, Tuple], base_type: Type[NT],
            field_to_parser: FieldToParser,
            field_parsers: List[AbstractParser]) -> NT:
        """
        Load a dictionary, list, or tuple to a `NamedTuple` sub-class
        """

    @staticmethod
    @abstractmethod
    def load_to_named_tuple_untyped(
            o: Union[Dict, List, Tuple], base_type: Type[NT],
            dict_parser: AbstractParser, list_parser: AbstractParser) -> NT:
        """
        Load a dictionary, list, or tuple to a (generally) un-typed
        `collections.namedtuple`
        """

    @staticmethod
    @abstractmethod
    def load_to_dict(
            o: Dict, base_type: Type[M],
            key_parser: AbstractParser,
            val_parser: AbstractParser) -> M:
        """
        Load an object `o` into a new object of type `base_type` (generally a
        :class:`dict` or a sub-class of one)
        """

    @staticmethod
    @abstractmethod
    def load_to_defaultdict(
            o: Dict, base_type: Type[DD],
            default_factory: DefFactory,
            key_parser: AbstractParser,
            val_parser: AbstractParser) -> DD:
        """
        Load an object `o` into a new object of type `base_type` (generally a
        :class:`collections.defaultdict` or a sub-class of one)
        """

    @staticmethod
    @abstractmethod
    def load_to_typed_dict(
            o: Dict, base_type: Type[M],
            key_to_parser: FieldToParser,
            required_keys: FrozenKeys,
            optional_keys: FrozenKeys) -> M:
        """
        Load an object `o` annotated as a ``TypedDict`` sub-class into a new
        object of type `base_type` (generally a :class:`dict` or a sub-class
        of one)
        """

    @staticmethod
    @abstractmethod
    def load_to_decimal(o: N, base_type: Type[Decimal]) -> Decimal:
        """
        Load an object `o` into a new object of type `base_type` (generally a
        :class:`Decimal` or a sub-class of one)
        """

    @staticmethod
    @abstractmethod
    def load_to_datetime(
            o: Union[str, N], base_type: Type[datetime]) -> datetime:
        """
        Load a string or number (int or float) into a new object of type
        `base_type` (generally a :class:`datetime` or a sub-class of one)
        """

    @staticmethod
    @abstractmethod
    def load_to_time(o: str, base_type: Type[time]) -> time:
        """
        Load a string or number (int or float) into a new object of type
        `base_type` (generally a :class:`time` or a sub-class of one)
        """

    @staticmethod
    @abstractmethod
    def load_to_date(o: Union[str, N], base_type: Type[date]) -> date:
        """
        Load a string or number (int or float) into a new object of type
        `base_type` (generally a :class:`date` or a sub-class of one)
        """

    @staticmethod
    @abstractmethod
    def load_to_timedelta(
            o: Union[str, N], base_type: Type[timedelta]) -> timedelta:
        """
        Load a string or number (int or float) into a new object of type
        `base_type` (generally a :class:`timedelta` or a sub-class of one)
        """

    @classmethod
    @abstractmethod
    def get_parser_for_annotation(cls, ann_type: Type[T],
                                  base_cls: Type = None,
                                  extras: Extras = None) -> AbstractParser:
        """
        Returns the Parser (dispatcher) for a given annotation type.

        `base_cls` is the original class object, this is useful when the
        annotated type is a :class:`typing.ForwardRef` object
        """


class AbstractDumper(ABC):
    __slots__ = ()

    def __pre_as_dict__(self):
        """
        Optional hook that runs before the dataclass instance is processed and
        before it is converted to a dictionary object via :meth:`to_dict`.

        To override this, subclasses need to extend from :class:`DumpMixIn`
        and implement this method. A simple example is shown below:

        >>> from dataclasses import dataclass
        >>> from dataclass_wizard import JSONSerializable, DumpMixin
        >>>
        >>>
        >>> @dataclass
        >>> class MyClass(JSONSerializable, DumpMixin):
        >>>     my_str: str
        >>>
        >>>     def __pre_as_dict__(self):
        >>>         self.my_str = self.my_str.swapcase()

        """
