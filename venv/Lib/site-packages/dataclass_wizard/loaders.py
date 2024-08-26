from collections import defaultdict, deque, namedtuple
from dataclasses import is_dataclass
from datetime import datetime, time, date, timedelta
from decimal import Decimal
from enum import Enum
from typing import (
    Any, Type, Dict, List, Tuple, Iterable, Sequence, Union,
    NamedTupleMeta, SupportsFloat, AnyStr, Text, Callable, Optional
)
from uuid import UUID

from .abstractions import AbstractLoader, AbstractParser, FieldToParser
from .bases import BaseLoadHook, AbstractMeta, META
from .class_helper import (
    get_class_name, create_new_class,
    dataclass_to_loader, set_class_loader,
    dataclass_field_to_load_parser, json_field_to_dataclass_field,
    _CLASS_TO_LOAD_FUNC, dataclass_fields, get_meta, is_subclass_safe,
)
from .constants import _LOAD_HOOKS, SINGLE_ARG_ALIAS, IDENTITY
from .decorators import _alias, _single_arg_alias, resolve_alias_func, _identity
from .errors import ParseError, MissingFields, UnknownJSONKey, MissingData
from .log import LOG
from .models import Extras, _PatternedDT
from .parsers import *
from .type_def import (
    ExplicitNull, FrozenKeys, DefFactory, NoneType, JSONObject,
    M, N, T, E, U, DD, LSQ, NT
)
from .utils.string_conv import to_snake_case
from .utils.type_conv import (
    as_bool, as_str, as_datetime, as_date, as_time, as_int, as_timedelta
)
from .utils.typing_compat import (
    is_literal, is_typed_dict, get_origin, get_args, is_annotated,
    eval_forward_ref_if_needed
)


class LoadMixin(AbstractLoader, BaseLoadHook):
    """
    This Mixin class derives its name from the eponymous `json.loads`
    function. Essentially it contains helper methods to convert JSON strings
    (or a Python dictionary object) to a `dataclass` which can often contain
    complex types such as lists, dicts, or even other dataclasses nested
    within it.

    Refer to the :class:`AbstractLoader` class for documentation on any of the
    implemented methods.

    """
    __slots__ = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
        setup_default_loader(cls)

    @staticmethod
    @_alias(to_snake_case)
    def transform_json_field(string: str) -> str:
        # alias: to_snake_case
        ...

    @staticmethod
    @_identity
    def default_load_to(o: T, _: Any) -> T:
        # identity: o
        ...

    @staticmethod
    def load_after_type_check(o: Any, base_type: Type[T]) -> T:

        if isinstance(o, base_type):
            return o

        e = ValueError(f'data type is not a {base_type!s}')
        raise ParseError(e, o, base_type)

    @staticmethod
    @_alias(as_str)
    def load_to_str(o: Union[Text, N, None], base_type: Type[str]) -> str:
        # alias: as_str
        ...

    @staticmethod
    @_alias(as_int)
    def load_to_int(o: Union[str, int, bool, None], base_type: Type[N]) -> N:
        # alias: as_int
        ...

    @staticmethod
    @_single_arg_alias('base_type')
    def load_to_float(o: Union[SupportsFloat, str], base_type: Type[N]) -> N:
        # alias: base_type(o)
        ...

    @staticmethod
    @_single_arg_alias(as_bool)
    def load_to_bool(o: Union[str, bool, N], _: Type[bool]) -> bool:
        # alias: as_bool(o)
        ...

    @staticmethod
    @_single_arg_alias('base_type')
    def load_to_enum(o: Union[AnyStr, N], base_type: Type[E]) -> E:
        # alias: base_type(o)
        ...

    @staticmethod
    @_single_arg_alias('base_type')
    def load_to_uuid(o: Union[AnyStr, U], base_type: Type[U]) -> U:
        # alias: base_type(o)
        ...

    @staticmethod
    def load_to_iterable(
            o: Iterable, base_type: Type[LSQ],
            elem_parser: AbstractParser) -> LSQ:

        return base_type([elem_parser(elem) for elem in o])

    @staticmethod
    def load_to_tuple(
            o: Union[List, Tuple], base_type: Type[Tuple],
            elem_parsers: Sequence[AbstractParser]) -> Tuple:

        try:
            zipped = zip(elem_parsers, o)
        except TypeError:
            return base_type([e for e in o])
        else:
            return base_type([parser(e) for parser, e in zipped])

    @staticmethod
    def load_to_named_tuple(
            o: Union[Dict, List, Tuple], base_type: Type[NT],
            field_to_parser: FieldToParser,
            field_parsers: List[AbstractParser]) -> NT:

        if isinstance(o, dict):
            # Convert the values of all fields in the NamedTuple, using
            # their type annotations. The keys in a dictionary object
            # (assuming it was loaded from JSON) are required to be
            # strings, so we don't need to convert them.
            return base_type(
                **{k: field_to_parser[k](o[k]) for k in o})
        # We're passed in a list or a tuple.
        return base_type(
            *[parser(elem) for parser, elem in zip(field_parsers, o)])

    @staticmethod
    def load_to_named_tuple_untyped(
            o: Union[Dict, List, Tuple], base_type: Type[NT],
            dict_parser: AbstractParser, list_parser: AbstractParser) -> NT:

        if isinstance(o, dict):
            return base_type(**dict_parser(o))
        # We're passed in a list or a tuple.
        return base_type(*list_parser(o))

    @staticmethod
    def load_to_dict(
            o: Dict, base_type: Type[M],
            key_parser: AbstractParser,
            val_parser: AbstractParser) -> M:

        return base_type(
            (key_parser(k), val_parser(v))
            for k, v in o.items()
        )

    @staticmethod
    def load_to_defaultdict(
            o: Dict, base_type: Type[DD],
            default_factory: DefFactory,
            key_parser: AbstractParser,
            val_parser: AbstractParser) -> DD:

        return base_type(
            default_factory,
            {key_parser(k): val_parser(v)
             for k, v in o.items()}
        )

    @staticmethod
    def load_to_typed_dict(
            o: Dict, base_type: Type[M],
            key_to_parser: FieldToParser,
            required_keys: FrozenKeys,
            optional_keys: FrozenKeys) -> M:

        kwargs = {}

        # Set required keys for the `TypedDict`
        for k in required_keys:
            kwargs[k] = key_to_parser[k](o[k])

        # Set optional keys for the `TypedDict` (if they exist)
        for k in optional_keys:
            if k in o:
                kwargs[k] = key_to_parser[k](o[k])

        return base_type(**kwargs)

    @staticmethod
    def load_to_decimal(o: N, base_type: Type[Decimal]) -> Decimal:

        return base_type(str(o))

    @staticmethod
    @_alias(as_datetime)
    def load_to_datetime(
            o: Union[str, N], base_type: Type[datetime]) -> datetime:
        # alias: as_datetime
        ...

    @staticmethod
    @_alias(as_time)
    def load_to_time(o: str, base_type: Type[time]) -> time:
        # alias: as_time
        ...

    @staticmethod
    @_alias(as_date)
    def load_to_date(o: Union[str, N], base_type: Type[date]) -> date:
        # alias: as_date
        ...

    @staticmethod
    @_alias(as_timedelta)
    def load_to_timedelta(
            o: Union[str, N], base_type: Type[timedelta]) -> timedelta:
        # alias: as_timedelta
        ...

    @classmethod
    def get_parser_for_annotation(cls, ann_type: Type[T],
                                  base_cls: Type = None,
                                  extras: Extras = None) -> AbstractParser:
        """Returns the Parser (dispatcher) for a given annotation type."""
        hooks = cls.__LOAD_HOOKS__
        ann_type = eval_forward_ref_if_needed(ann_type, base_cls)
        load_hook = hooks.get(ann_type)
        base_type = ann_type

        # TODO: I'll need to refactor the code below to remove the nested `if`
        #   statements, when time allows. Right now the branching logic is
        #   unseemly and there's really no need for that, as any such
        #   performance gains (if they do exist) are minimal at best.

        if 'pattern' in extras and is_subclass_safe(
                ann_type, (date, time, datetime)):
            # Check for a field that was initially annotated like:
            #   Annotated[List[time], Pattern('%H:%M:%S')]
            return PatternedDTParser(base_cls, extras, base_type)

        if load_hook is None:
            # Need to check this first, because the `Literal` type in Python
            # 3.6 behaves a bit differently (doesn't have an `__origin__`
            # attribute for example)
            if is_literal(ann_type):
                return LiteralParser(base_cls, extras, ann_type)

            if is_annotated(ann_type):
                # Given `Annotated[T, MaxValue(10), ...]`, we only need `T`
                ann_type = get_args(ann_type)[0]
                return cls.get_parser_for_annotation(
                    ann_type, base_cls, extras)

            # This property will be available for most generic types in the
            # `typing` library.
            try:
                base_type = get_origin(ann_type, raise_=True)

            # If we can't access this property, it's likely a non-generic
            # class or a non-generic sub-type.
            except AttributeError:

                # https://stackoverflow.com/questions/76520264/dataclasswizard-after-upgrading-to-python3-11-is-not-working-as-expected
                if base_type is Any:
                    load_hook = cls.default_load_to

                elif isinstance(base_type, type):

                    if is_dataclass(base_type):
                        base_type: Type[T]
                        load_hook = load_func_for_dataclass(
                            base_type,
                            is_main_class=False,
                            config=extras['config']
                        )

                    elif issubclass(base_type, Enum):
                        load_hook = hooks.get(Enum)

                    elif issubclass(base_type, UUID):
                        load_hook = hooks.get(UUID)

                    elif issubclass(base_type, tuple) \
                            and hasattr(base_type, '_fields'):

                        if getattr(base_type, '__annotations__', None):
                            # Annotated as a `typing.NamedTuple` subtype
                            load_hook = hooks.get(NamedTupleMeta)
                            return NamedTupleParser(
                                base_cls, extras, base_type, load_hook,
                                cls.get_parser_for_annotation
                            )
                        else:
                            # Annotated as a `collections.namedtuple` subtype
                            load_hook = hooks.get(namedtuple)
                            return NamedTupleUntypedParser(
                                base_cls, extras, base_type, load_hook,
                                cls.get_parser_for_annotation
                            )

                    elif is_typed_dict(base_type):
                        load_hook = cls.load_to_typed_dict
                        return TypedDictParser(
                            base_cls, extras, base_type, load_hook,
                            cls.get_parser_for_annotation
                        )

                elif isinstance(base_type, _PatternedDT):
                    # Check for a field that was initially annotated like:
                    #   DateTimePattern('%m/%d/%y %H:%M:%S')]
                    return PatternedDTParser(base_cls, extras, base_type)

                elif base_type is Ellipsis:
                    load_hook = cls.default_load_to

                # If we can't find the underlying type of the object, we
                # should emit a warning for awareness.
                else:
                    load_hook = cls.default_load_to
                    LOG.warning('Using default loader, type=%r', ann_type)

            # Else, it's annotated with a generic type like Union or List -
            # basically anything that's subscriptable.
            else:
                if base_type is Union:
                    # Get the subscripted values
                    #   ex. `Union[int, str]` -> (int, str)
                    base_types = get_args(ann_type)

                    if not base_types:
                        # Annotated as just `Union` (no subscripted types)
                        load_hook = cls.default_load_to

                    elif NoneType in base_types and len(base_types) == 2:
                        # Special case for Optional[x], which is actually Union[x, None]
                        return OptionalParser(
                            base_cls, extras, base_types[0],
                            cls.get_parser_for_annotation
                        )

                    else:
                        return UnionParser(
                            base_cls, extras, base_types,
                            cls.get_parser_for_annotation
                        )

                elif issubclass(base_type, defaultdict):
                    load_hook = hooks[defaultdict]
                    return DefaultDictParser(
                        base_cls, extras, ann_type, load_hook,
                        cls.get_parser_for_annotation
                    )

                elif issubclass(base_type, dict):
                    load_hook = hooks[dict]
                    return MappingParser(
                        base_cls, extras, ann_type, load_hook,
                        cls.get_parser_for_annotation
                    )

                elif issubclass(base_type, LSQ.__constraints__):
                    load_hook = cls.load_to_iterable
                    return IterableParser(
                        base_cls, extras, ann_type, load_hook,
                        cls.get_parser_for_annotation
                    )

                elif issubclass(base_type, tuple):
                    load_hook = hooks[tuple]
                    # Check if the `Tuple` appears in the variadic form
                    #   i.e. Tuple[str, ...]
                    args = get_args(ann_type)
                    is_variadic = args and args[-1] is ...
                    # Determine the parser for the annotation
                    parser: Type[AbstractParser] = TupleParser
                    if is_variadic:
                        parser = VariadicTupleParser

                    return parser(
                        base_cls, extras, ann_type, load_hook,
                        cls.get_parser_for_annotation
                    )

                else:
                    load_hook = hooks.get(base_type)

        # TODO i'll need to refactor this to remove duplicate lines above -
        # maybe merge them together.
        elif issubclass(base_type, dict):
            load_hook = hooks[dict]
            return MappingParser(
                base_cls, extras, ann_type, load_hook,
                cls.get_parser_for_annotation)

        elif issubclass(base_type, LSQ.__constraints__):
            load_hook = cls.load_to_iterable
            return IterableParser(
                base_cls, extras, ann_type, load_hook,
                cls.get_parser_for_annotation)

        elif issubclass(base_type, tuple):
            load_hook = hooks[tuple]
            return TupleParser(
                base_cls, extras, ann_type, load_hook,
                cls.get_parser_for_annotation)

        if load_hook is None:
            # If load hook is still not resolved at this point, it's possible
            # the type is a subclass of a known type.
            for typ in hooks:
                # TODO use a `is_subclass_safe` helper function instead
                try:
                    if issubclass(base_type, typ):
                        load_hook = hooks[typ]
                        break
                except TypeError:
                    continue

            else:
                # No matching hook is found for the type.
                err = TypeError('Provided type is not currently supported.')
                raise ParseError(
                    err, None, base_type,
                    unsupported_type=base_type
                )

        if hasattr(load_hook, SINGLE_ARG_ALIAS):
            load_hook = resolve_alias_func(load_hook, locals())
            return SingleArgParser(base_cls, extras, base_type, load_hook)

        if hasattr(load_hook, IDENTITY):
            return IdentityParser(base_type, extras, base_type)

        return Parser(base_cls, extras, base_type, load_hook)


def setup_default_loader(cls=LoadMixin):
    """
    Setup the default type hooks to use when converting `str` (json) or a
    Python `dict` object to a `dataclass` instance.

    Note: `cls` must be :class:`LoadMixIn` or a sub-class of it.
    """
    # Simple types
    cls.register_load_hook(str, cls.load_to_str)
    cls.register_load_hook(int, cls.load_to_int)
    cls.register_load_hook(float, cls.load_to_float)
    cls.register_load_hook(bool, cls.load_to_bool)
    cls.register_load_hook(bytes, cls.load_after_type_check)
    cls.register_load_hook(bytearray, cls.load_after_type_check)
    cls.register_load_hook(NoneType, cls.default_load_to)
    # Complex types
    cls.register_load_hook(Enum, cls.load_to_enum)
    cls.register_load_hook(UUID, cls.load_to_uuid)
    cls.register_load_hook(set, cls.load_to_iterable)
    cls.register_load_hook(frozenset, cls.load_to_iterable)
    cls.register_load_hook(deque, cls.load_to_iterable)
    cls.register_load_hook(list, cls.load_to_iterable)
    cls.register_load_hook(tuple, cls.load_to_tuple)
    # noinspection PyTypeChecker
    cls.register_load_hook(namedtuple, cls.load_to_named_tuple_untyped)
    cls.register_load_hook(NamedTupleMeta, cls.load_to_named_tuple)
    cls.register_load_hook(defaultdict, cls.load_to_defaultdict)
    cls.register_load_hook(dict, cls.load_to_dict)
    cls.register_load_hook(Decimal, cls.load_to_decimal)
    # Dates and times
    cls.register_load_hook(datetime, cls.load_to_datetime)
    cls.register_load_hook(time, cls.load_to_time)
    cls.register_load_hook(date, cls.load_to_date)
    cls.register_load_hook(timedelta, cls.load_to_timedelta)


def get_loader(class_or_instance=None, create=True) -> Type[LoadMixin]:
    """
    Get the loader for the class, using the following logic:

        * Return the class if it's already a sub-class of :class:`LoadMixin`
        * If `create` is enabled (which is the default), a new sub-class of
          :class:`LoadMixin` for the class will be generated and cached on the
          initial run.
        * Otherwise, we will return the base loader, :class:`LoadMixin`, which
          can potentially be shared by more than one dataclass.

    """
    try:
        return dataclass_to_loader(class_or_instance)

    except KeyError:

        if hasattr(class_or_instance, _LOAD_HOOKS):
            return set_class_loader(class_or_instance, class_or_instance)

        elif create:
            cls_loader = create_new_class(class_or_instance, (LoadMixin, ))
            return set_class_loader(class_or_instance, cls_loader)

        return set_class_loader(class_or_instance, LoadMixin)


def fromdict(cls: Type[T], d: JSONObject) -> T:
    """
    Converts a Python dictionary object to a dataclass instance.

    Iterates over each dataclass field recursively; lists, dicts, and nested
    dataclasses will likewise be initialized as expected.

    When directly invoking this function, an optional Meta configuration for
    the dataclass can be specified via ``LoadMeta``; by default, this will
    apply recursively to any nested dataclasses. Here's a sample usage of this
    below::

        >>> LoadMeta(key_transform='CAMEL').bind_to(MyClass)
        >>> fromdict(MyClass, {"myStr": "value"})

    """
    try:
        load = _CLASS_TO_LOAD_FUNC[cls]
    except KeyError:
        load = load_func_for_dataclass(cls)

    return load(d)


def fromlist(cls: Type[T], list_of_dict: List[JSONObject]) -> List[T]:
    """
    Converts a Python list object to a list of dataclass instances.

    Iterates over each dataclass field recursively; lists, dicts, and nested
    dataclasses will likewise be initialized as expected.

    """
    try:
        load = _CLASS_TO_LOAD_FUNC[cls]
    except KeyError:
        load = load_func_for_dataclass(cls)

    return [load(d) for d in list_of_dict]


def load_func_for_dataclass(
        cls: Type[T],
        is_main_class: bool = True,
        config: Optional[META] = None) -> Callable[[JSONObject], T]:

    # Get the loader for the class, or create a new one as needed.
    cls_loader = get_loader(cls)

    # Get the meta config for the class, or the default config otherwise.
    meta = get_meta(cls)

    if is_main_class:  # we are being run for the main dataclass
        # If the `recursive` flag is enabled and a Meta config is provided,
        # apply the Meta recursively to any nested classes.
        if meta.recursive and meta is not AbstractMeta:
            config = meta

    else:  # we are being run for a nested dataclass
        if config:
            # we want to apply the meta config from the main dataclass
            # recursively.
            meta = meta | config
            meta.bind_to(cls, is_default=False)

    # This contains a mapping of the original field name to the parser for its
    # annotated type; the item lookup *can* be case-insensitive.
    field_to_parser = dataclass_field_to_load_parser(cls_loader, cls, config)

    # A cached mapping of each key in a JSON or dictionary object to the
    # resolved dataclass field name; useful so we don't need to do a case
    # transformation (via regex) each time.
    json_to_dataclass_field = json_field_to_dataclass_field(cls)

    def cls_fromdict(o: JSONObject, *_):
        """
        De-serialize a dictionary `o` to an instance of a dataclass `cls`.
        """

        # Need to create a separate dictionary to copy over the constructor
        # args, as we don't want to mutate the original dictionary object.
        cls_kwargs = {}

        # This try-block is here in case the object `o` is None.
        try:
            # Loop over the dictionary object
            for json_key in o:

                # Get the resolved dataclass field name
                try:
                    field_name = json_to_dataclass_field[json_key]
                    # Exclude JSON keys that don't map to any fields.
                    if field_name is ExplicitNull:
                        continue

                except KeyError:
                    try:
                        field_name = lookup_field_for_json_key(o, json_key)
                    except LookupError:
                        continue

                try:
                    # Note: pass the original cased field to the class
                    # constructor; don't use the lowercase result from
                    # `transform_json_field`
                    cls_kwargs[field_name] = field_to_parser[field_name](
                        o[json_key])

                except ParseError as e:
                    # We run into a parsing error while loading the field
                    # value; Add additional info on the Exception object
                    # before re-raising it.
                    #
                    # First confirm these values are not already set by an
                    # inner dataclass. If so, it likely makes it easier to
                    # debug the cause. Note that this should already be
                    # handled by the `setter` methods.
                    e.class_name = cls
                    e.field_name = field_name
                    e.json_object = o
                    raise

        except TypeError:
            # If the object `o` is None, then raise an error with the relevant
            # info included.
            if o is None:
                raise MissingData(cls) from None

            # Check if the object `o` is some other type than what we expect -
            # for example, we could be passed in a `list` type instead.
            if not isinstance(o, dict):
                e = TypeError('Incorrect type for field')
                raise ParseError(
                    e, o, dict, cls,
                    desired_type=dict
                ) from None

            #  Else, just re-raise the error.
            raise

        # Now pass the arguments to the constructor method, and return the new
        # dataclass instance. If there are any missing fields, we raise them
        # here.

        try:
            return cls(**cls_kwargs)

        except TypeError as e:
            raise MissingFields(
                e, o, cls, cls_kwargs, dataclass_fields(cls)
            ) from None

    def lookup_field_for_json_key(o: JSONObject, json_field: str):
        """
        Determines the dataclass field which a JSON key should map to. Note
        this only runs the initial time, i.e. the first time we encounter the
        key in a JSON object.

        :raises LookupError: If there no resolved field name for the JSON key.
        :raises UnknownJSONKey: If there is no resolved field name for the
          JSON key, and`raise_on_unknown_json_key` is enabled in the Meta
          config for the class.
        """

        # Short path: an identical-cased field name exists for the JSON key
        if json_field in field_to_parser:
            json_to_dataclass_field[json_field] = json_field
            return json_field

        # Transform JSON field name (typically camel-cased) to the
        # snake-cased variant which is convention in Python.
        transformed_field = cls_loader.transform_json_field(json_field)

        try:
            # Do a case-insensitive lookup of the dataclass field, and
            # cache the mapping, so we have it for next time
            field_name = field_to_parser.get_key(transformed_field)
            json_to_dataclass_field[json_field] = field_name

        except KeyError:
            # Else, we see an unknown field in the dictionary object
            json_to_dataclass_field[json_field] = ExplicitNull
            LOG.warning(
                'JSON field %r missing from dataclass schema, '
                'class=%r, parsed field=%r',
                json_field, get_class_name(cls), transformed_field)

            # Raise an error here (if needed)
            if meta.raise_on_unknown_json_key:
                cls_fields = dataclass_fields(cls)
                e = UnknownJSONKey(json_field, o, cls, cls_fields)
                raise e from None

            raise LookupError

        return field_name

    # Save the load function for the main dataclass, so we don't need to run
    # this logic each time.
    if is_main_class:
        _CLASS_TO_LOAD_FUNC[cls] = cls_fromdict

    return cls_fromdict
