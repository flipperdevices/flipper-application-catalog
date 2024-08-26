from collections import defaultdict
from dataclasses import MISSING, Field, fields
from typing import Dict, Tuple, Type, Union, Callable, Optional, Any

from .abstractions import W, AbstractLoader, AbstractDumper, AbstractParser
from .bases import M, AbstractMeta
from .models import JSONField, JSON, Extras, _PatternedDT
from .type_def import ExplicitNull, ExplicitNullType, T
from .utils.dict_helper import DictWithLowerStore
from .utils.typing_compat import (
    is_annotated, get_args, eval_forward_ref_if_needed
)


# A cached mapping of dataclass to the list of fields, as returned by
# `dataclasses.fields()`.
_FIELDS: Dict[Type, Tuple[Field]] = {}

# Mapping of main dataclass to its `load` function.
_CLASS_TO_LOAD_FUNC: Dict[Type, Any] = {}

# Mapping of main dataclass to its `dump` function.
_CLASS_TO_DUMP_FUNC: Dict[Type, Any] = {}

# A mapping of dataclass to its loader.
_CLASS_TO_LOADER: Dict[Type, Type[AbstractLoader]] = {}

# A mapping of dataclass to its dumper.
_CLASS_TO_DUMPER: Dict[Type, Type[AbstractDumper]] = {}

# A cached mapping of a dataclass to each of its case-insensitive field names
# and load hook.
#
# Note: need to create a `ForwardRef` here, because Python 3.6 complains.
_FIELD_NAME_TO_LOAD_PARSER: Dict[
    Type, 'DictWithLowerStore[str, AbstractParser]'] = {}

# Since the dump process doesn't use Parsers currently, we use a sentinel
# mapping to confirm if we need to setup the dump config for a dataclass
# on an initial run.
_IS_DUMP_CONFIG_SETUP: Dict[Type, bool] = {}

# A cached mapping, per dataclass, of JSON field to instance field name
_JSON_FIELD_TO_DATACLASS_FIELD: Dict[
    Type, Dict[str, Union[str, ExplicitNullType]]] = defaultdict(dict)

# A cached mapping, per dataclass, of instance field name to JSON field
_DATACLASS_FIELD_TO_JSON_FIELD: Dict[Type, Dict[str, str]] = defaultdict(dict)

# A mapping of dataclass name to its Meta initializer (defined in
# :class:`bases.BaseJSONWizardMeta`), which is only set when the
# :class:`JSONSerializable.Meta` is sub-classed.
_META_INITIALIZER: Dict[
    str, Callable[[Type[W]], None]] = {}


# Mapping of dataclass to its Meta inner class, which will only be set when
# the :class:`JSONSerializable.Meta` is sub-classed.
_META: Dict[Type, M] = {}


def dataclass_to_loader(cls):
    """
    Returns the loader for a dataclass.
    """
    return _CLASS_TO_LOADER[cls]


def dataclass_to_dumper(cls: Type):
    """
    Returns the dumper for a dataclass.
    """
    return _CLASS_TO_DUMPER[cls]


def set_class_loader(class_or_instance, loader: Type[AbstractLoader]):
    """
    Set (and return) the loader for a dataclass.
    """
    cls = get_class(class_or_instance)
    loader_cls = get_class(loader)

    _CLASS_TO_LOADER[cls] = get_class(loader_cls)

    return _CLASS_TO_LOADER[cls]


def set_class_dumper(cls: Type, dumper: Type[AbstractDumper]):
    """
    Set (and return) the dumper for a dataclass.
    """
    _CLASS_TO_DUMPER[cls] = get_class(dumper)

    return _CLASS_TO_DUMPER[cls]


def json_field_to_dataclass_field(cls: Type):
    """
    Returns a mapping of JSON field to dataclass field.
    """
    return _JSON_FIELD_TO_DATACLASS_FIELD[cls]


def dataclass_field_to_json_field(cls):
    """
    Returns a mapping of dataclass field to JSON field.
    """
    return _DATACLASS_FIELD_TO_JSON_FIELD[cls]


def dataclass_field_to_load_parser(
        cls_loader: Type[AbstractLoader],
        cls: Type,
        config: M,
        save: bool = True) -> 'DictWithLowerStore[str, AbstractParser]':
    """
    Returns a mapping of each lower-cased field name to its annotated type.
    """
    if cls not in _FIELD_NAME_TO_LOAD_PARSER:
        return _setup_load_config_for_cls(cls_loader, cls, config, save)

    return _FIELD_NAME_TO_LOAD_PARSER[cls]


def _setup_load_config_for_cls(cls_loader: Type[AbstractLoader],
                               cls: Type,
                               config: M,
                               save: bool = True
                               ) -> 'DictWithLowerStore[str, AbstractParser]':
    """
    This function processes a class `cls` on an initial run, and sets up the
    load process for `cls` by iterating over each dataclass field. For each
    field, it performs the following tasks:

        * Lookup the Parser (dispatcher) for the field based on its type
          annotation, and then cache it so we don't need to lookup each time.

        * Check if the field's annotation is of type ``Annotated``. If so,
          we iterate over each ``Annotated`` argument and find any special
          :class:`JSON` objects (this can also be set via the helper function
          ``json_key``). Assuming we find it, the class-specific mapping of
          JSON key to dataclass field name is then updated with the input
          passed in to this object.

        * Check if the field type is a :class:`JSONField` object (this can
          also be set by the helper function ``json_field``). Assuming this is
          the case, the class-specific mapping of JSON key to dataclass field
          name is then updated with the input passed in to the :class:`JSON`
          attribute.
    """
    json_to_dataclass_field = _JSON_FIELD_TO_DATACLASS_FIELD[cls]
    name_to_parser = {}

    for f in dataclass_init_fields(cls):
        field_extras: Extras = {'config': config}

        f.type = eval_forward_ref_if_needed(f.type, cls)
        field_type = f.type

        # Check if the field is a `Field` type or a subclass. If so, update
        # the class-specific mapping of JSON key to dataclass field name.
        if isinstance(f, Field):

            if isinstance(f, JSONField):
                for key in f.json.keys:
                    json_to_dataclass_field[key] = f.name

            else:
                value = f.metadata.get('__remapping__')
                if value and isinstance(value, JSON):
                    for key in value.keys:
                        json_to_dataclass_field[key] = f.name

        # Check if the field annotation is an `Annotated` type. If so,
        # look for any `JSON` objects in the arguments; for each object,
        # update the class-specific mapping of JSON key to dataclass field
        # name.
        if is_annotated(field_type):
            ann_type, *extras = get_args(field_type)
            for extra in extras:
                if isinstance(extra, JSON):
                    for key in extra.keys:
                        json_to_dataclass_field[key] = f.name
                elif isinstance(extra, _PatternedDT):
                    field_extras['pattern'] = extra

        # Lookup the Parser (dispatcher) for each field based on its annotated
        # type, and then cache it so we don't need to lookup each time.
        name_to_parser[f.name] = cls_loader.get_parser_for_annotation(
            field_type, cls, field_extras
        )

    parser_dict = DictWithLowerStore(name_to_parser)
    # only cache the load parser for the class if `save` is enabled
    if save:
        _FIELD_NAME_TO_LOAD_PARSER[cls] = parser_dict

    return parser_dict


def setup_dump_config_for_cls_if_needed(cls: Type):
    """
    This function processes a class `cls` on an initial run, and sets up the
    dump process for `cls` by iterating over each dataclass field. For each
    field, it performs the following tasks:

        * Check if the field's annotation is of type ``Annotated``. If so,
          we iterate over each ``Annotated`` argument and find any special
          :class:`JSON` objects (this can also be set via the helper function
          ``json_key``). Assuming we find it, the class-specific mapping of
          dataclass field name to JSON key is then updated with the input
          passed in to this object.

        * Check if the field type is a :class:`JSONField` object (this can
          also be set by the helper function ``json_field``). Assuming this is
          the case, the class-specific mapping of dataclass field name to JSON
          key is then updated with the input passed in to the :class:`JSON`
          attribute.
    """

    if cls in _IS_DUMP_CONFIG_SETUP:
        return

    dataclass_to_json_field = _DATACLASS_FIELD_TO_JSON_FIELD[cls]

    for f in dataclass_fields(cls):

        # Check if the field is a `Field` type or a subclass. If so, update
        # the class-specific mapping of dataclass field name to JSON key.
        if isinstance(f, Field):

            if isinstance(f, JSONField):
                if not f.json.dump:
                    dataclass_to_json_field[f.name] = ExplicitNull
                elif f.json.all:
                    dataclass_to_json_field[f.name] = f.json.keys[0]

            else:
                value = f.metadata.get('__remapping__')
                if value and isinstance(value, JSON) and value.all:
                    dataclass_to_json_field[f.name] = value.keys[0]

        # Check if the field annotation is an `Annotated` type. If so,
        # look for any `JSON` objects in the arguments; for each object,
        # update the class-specific mapping of dataclass field name to JSON
        # key.
        f.type = eval_forward_ref_if_needed(f.type, cls)
        if is_annotated(f.type):
            for extra in get_args(f.type)[1:]:
                if isinstance(extra, JSON):
                    if not extra.dump:
                        dataclass_to_json_field[f.name] = ExplicitNull
                    elif extra.all:
                        dataclass_to_json_field[f.name] = extra.keys[0]

    # Mark the dataclass as processed, as the initial dump process is set up.
    _IS_DUMP_CONFIG_SETUP[cls] = True


def call_meta_initializer_if_needed(cls: Type[W]):
    """
    Calls the Meta initializer when the inner :class:`Meta` is sub-classed.
    """
    cls_name = get_class_name(cls)

    if cls_name in _META_INITIALIZER:
        _META_INITIALIZER[cls_name](cls)


def get_meta(cls: Type) -> M:
    """
    Retrieves the Meta config for the :class:`AbstractJSONWizard` subclass.

    This config is set when the inner :class:`Meta` is sub-classed.
    """
    return _META.get(cls, AbstractMeta)


def dataclass_fields(cls) -> Tuple[Field]:
    """
    Cache the `dataclasses.fields()` call for each class, as overall that
    ends up around 5x faster than making a fresh call each time.

    """
    if cls not in _FIELDS:
        _FIELDS[cls] = fields(cls)

    return _FIELDS[cls]


def dataclass_init_fields(cls) -> Tuple[Field]:
    """Get only the dataclass fields that would be passed into the constructor."""
    return tuple(f for f in dataclass_fields(cls) if f.init)


def dataclass_field_names(cls) -> Tuple[str, ...]:
    """Get the names of all dataclass fields"""
    return tuple(f.name for f in dataclass_fields(cls))


def dataclass_field_to_default(cls) -> Dict[str, Any]:
    """Get default values for the (optional) dataclass fields."""
    defaults = {}
    for f in dataclass_fields(cls):
        if f.default is not MISSING:
            defaults[f.name] = f.default
        elif f.default_factory is not MISSING:
            defaults[f.name] = f.default_factory()

    return defaults


def create_new_class(
        class_or_instance, bases: Tuple[T, ...],
        suffix: Optional[str] = None, attr_dict=None) -> T:
    """
    Create (dynamically) and return a new class that sub-classes from a list
    of `bases`.
    """
    if not suffix and bases:
        suffix = get_class_name(bases[0])

    new_cls_name = f'{get_class_name(class_or_instance)}{suffix}'

    return type(
        new_cls_name,
        bases,
        attr_dict or {'__slots__': ()}
    )


def get_class_name(class_or_instance) -> str:
    """Return the fully qualified name of a class."""
    try:
        return class_or_instance.__qualname__
    except AttributeError:
        # We're dealing with a dataclass instance
        return type(class_or_instance).__qualname__


def get_outer_class_name(inner_cls, default=None, raise_=True):
    """
    Attempt to return the fully qualified name of the outer (enclosing) class,
    given a reference to the inner class.

    If any errors occur - such as when `inner_cls` is not a real inner
    class - then an error will be raised if `raise_` is true, and if not
    we will return `default` instead.

    """
    try:
        name = get_class_name(inner_cls).rsplit('.', 1)[-2]
        # This is mainly for our test cases, where we nest the class
        # definition in the test func. Either way, it's not a valid class.
        assert not name.endswith('<locals>')

    except (IndexError, AssertionError):
        if raise_:
            raise
        return default

    else:
        return name


def get_class(obj):
    """Get the class for an object `obj`"""
    return obj if isinstance(obj, type) else type(obj)


def is_subclass(obj, base_cls: Type) -> bool:
    """Check if `obj` is a sub-class of `base_cls`"""
    cls = obj if isinstance(obj, type) else type(obj)
    return issubclass(cls, base_cls)


def is_subclass_safe(cls, class_or_tuple) -> bool:
    """Check if `obj` is a sub-class of `base_cls` (safer version)"""
    try:
        return issubclass(cls, class_or_tuple)
    except TypeError:
        return cls is class_or_tuple
