from abc import ABCMeta, abstractmethod
from typing import Callable, Type, Dict, Optional, ClassVar, Union, TypeVar

from .constants import TAG
from .decorators import cached_class_property
from .enums import DateTimeTo, LetterCase
from .type_def import FrozenKeys


# Create a generic variable that can be 'AbstractMeta', or any subclass.
M = TypeVar('M', bound='AbstractMeta')
# Use `Type` here explicitly, because we will never have an `M` object.
M = Type[M]
META = M  # alias, since `M` is already defined in another module


class ABCOrAndMeta(ABCMeta):
    """
    Metaclass to add class-level :meth:`__or__` and :meth:`__and__` methods
    to a base class of type :type:`M`.

    Ref:
      - https://stackoverflow.com/q/15008807/10237506
      - https://stackoverflow.com/a/57351066/10237506
    """

    def __or__(cls: M, other: M) -> M:
        """
        Merge two Meta configs. Priority will be given to the source config
        present in `cls`, e.g. the first operand in the '|' expression.

        Use case: Merge the Meta configs for two separate dataclasses into a
        single, unified Meta config.
        """
        src = cls
        src_dict = src.__dict__
        other_dict = other.__dict__

        base_dict = {'__slots__': ()}

        # Set meta attributes here.
        if src is AbstractMeta:
            # Here we can't use `src` because the `bind_to` method isn't
            # defined on the abstract class. Use `other` instead, which
            # *will* be a concrete subclass of `AbstractMeta`.
            src = other
            for k in src.fields_to_merge:
                if k in other_dict:
                    base_dict[k] = other_dict[k]
        else:
            for k in src.fields_to_merge:
                if k in src_dict:
                    base_dict[k] = src_dict[k]
                elif k in other_dict:
                    base_dict[k] = other_dict[k]

        # This mapping won't be updated. Use the src by default.
        for k in src.__special_attrs__:
            if k in src_dict:
                base_dict[k] = src_dict[k]

        new_cls_name = src.__name__
        # Check if the type of the class we want to create is
        # `JSONWizard.Meta` or a subclass. If so, we want to avoid the
        # mandatory `__init_subclass__` call that gets invoked when creating
        # a new class, so use the superclass type instead.
        if src.__is_inner_meta__:
            # In a reversed MRO, the inheritance tree looks like this:
            #   |___ object -> AbstractMeta -> BaseJSONWizardMeta -> ...
            # So here, we want to choose the third-to-last class in the list.
            src = src.__mro__[-3]

        # noinspection PyTypeChecker
        return type(new_cls_name, (src, ), base_dict)

    def __and__(cls: M, other: M) -> M:
        """
        Merge the `other` Meta config into the first one, i.e. `cls`. This
        operation does not create a new class, but instead it modifies the
        source config `cls` in-place; the source will be the first operand in
        the '&' expression.

        Use case: Merge a separate Meta config (for a single dataclass) with
        the first config.
        """
        other_dict = other.__dict__

        # Set meta attributes here.
        for k in cls.all_fields:
            if k in other_dict:
                setattr(cls, k, other_dict[k])

        return cls


class AbstractMeta(metaclass=ABCOrAndMeta):
    """
    Base class definition for the `JSONWizard.Meta` inner class.
    """
    __slots__ = ()

    # A list of class attributes that are exclusive to the Meta config.
    # When merging two Meta configs for a class, these are the only
    # attributes which will *not* be merged.
    __special_attrs__ = frozenset({
        'recursive',
        'json_key_to_field',
        'tag',
    })

    # Class attribute which enables us to detect a `JSONWizard.Meta` subclass.
    __is_inner_meta__ = False

    # True to enable Debug mode for additional (more verbose) log output.
    #
    # For example, a message is logged whenever an unknown JSON key is
    # encountered when `from_dict` or `from_json` is called.
    #
    # This also results in more helpful messages during error handling, which
    # can be useful when debugging the cause when values are an invalid type
    # (i.e. they don't match the annotation for the field) when unmarshalling
    # a JSON object to a dataclass instance.
    #
    # Note there is a minor performance impact when DEBUG mode is enabled.
    debug_enabled: ClassVar[bool] = False

    # When enabled, a specified Meta config for the main dataclass (i.e. the
    # class on which `from_dict` and `to_dict` is called) will cascade down
    # and be merged with the Meta config for each *nested* dataclass; note
    # that during a merge, priority is given to the Meta config specified on
    # each class.
    #
    # The default behavior is True, so the Meta config (if provided) will
    # apply in a recursive manner.
    recursive: ClassVar[bool] = True

    # True to raise an class:`UnknownJSONKey` when an unmapped JSON key is
    # encountered when `from_dict` or `from_json` is called; an unknown key is
    # one that does not have a known mapping to a dataclass field.
    #
    # The default is to only log a "warning" for such cases, which is visible
    # when `debug_enabled` is true and logging is properly configured.
    raise_on_unknown_json_key: ClassVar[bool] = False

    # A customized mapping of JSON keys to dataclass fields, that is used
    # whenever `from_dict` or `from_json` is called.
    #
    # Note: this is in addition to the implicit field transformations, like
    #   "myStr" -> "my_str"
    #
    # If the reverse mapping is also desired (i.e. dataclass field to JSON
    # key), then specify the "__all__" key as a truthy value. If multiple JSON
    # keys are specified for a dataclass field, only the first one provided is
    # used in this case.
    json_key_to_field: ClassVar[Dict[str, str]] = None

    # How should :class:`time` and :class:`datetime` objects be serialized
    # when converted to a Python dictionary object or a JSON string.
    marshal_date_time_as: ClassVar[Union[DateTimeTo, str]] = None

    # How JSON keys should be transformed to dataclass fields.
    #
    # Note that this only applies to keys which are to be set on dataclass
    # fields; other fields such as the ones for `TypedDict` or `NamedTuple`
    # sub-classes won't be similarly transformed.
    key_transform_with_load: ClassVar[Union[LetterCase, str]] = None

    # How dataclass fields should be transformed to JSON keys.
    #
    # Note that this only applies to dataclass fields; other fields such as
    # the ones for `TypedDict` or `NamedTuple` sub-classes won't be similarly
    # transformed.
    key_transform_with_dump: ClassVar[Union[LetterCase, str]] = None

    # The field name that identifies the tag for a class.
    #
    # When set to a value, an :attr:`TAG` field will be populated in the
    # dictionary object in the dump (serialization) process. When loading
    # (or de-serializing) a dictionary object, the :attr:`TAG` field will be
    # used to load the corresponding dataclass, assuming the dataclass field
    # is properly annotated as a Union type, ex.:
    #   my_data: Union[Data1, Data2, Data3]
    tag: ClassVar[str] = None

    # The dictionary key that identifies the tag field for a class. This is
    # only set when the `tag` field or the `auto_assign_tags` flag is enabled
    # in the `Meta` config for a dataclass.
    #
    # Defaults to '__tag__' if not specified.
    tag_key: ClassVar[str] = TAG

    # Auto-assign the class name as a dictionary "tag" key, for any dataclass
    # fields which are in a `Union` declaration, ex.:
    #   my_data: Union[Data1, Data2, Data3]
    auto_assign_tags: ClassVar[bool] = False

    # Determines whether we should we skip / omit fields with default values
    # (based on the `default` or `default_factory` argument specified for
    # the :func:`dataclasses.field`) in the serialization process.
    skip_defaults: ClassVar[bool] = False

    # noinspection PyMethodParameters
    @cached_class_property
    def all_fields(cls) -> FrozenKeys:
        """Return a list of all class attributes"""
        return frozenset(AbstractMeta.__annotations__)

    # noinspection PyMethodParameters
    @cached_class_property
    def fields_to_merge(cls) -> FrozenKeys:
        """Return a list of class attributes, minus `__special_attrs__`"""
        return cls.all_fields - cls.__special_attrs__

    @classmethod
    @abstractmethod
    def bind_to(cls, dataclass: Type, create=True, is_default=True):
        """
        Initialize hook which applies the Meta config to `dataclass`, which is
        typically a subclass of :class:`JSONWizard`.

        :param dataclass: A class which has been decorated by the `@dataclass`
          decorator; typically this is a sub-class of :class:`JSONWizard`.
        :param create: When true, a separate loader/dumper will be created
          for the class. If disabled, this will access the root loader/dumper,
          so modifying this should affect global settings across all
          dataclasses that use the JSON load/dump process.
        :param is_default: When enabled, the Meta will be cached as the
          default Meta config for the dataclass. Defaults to true.

        """


class BaseLoadHook:
    """
    Container class for type hooks.
    """
    __slots__ = ()

    __LOAD_HOOKS__: ClassVar[Dict[Type, Callable]] = None

    def __init_subclass__(cls):
        super().__init_subclass__()
        # (Re)assign the dict object so we have a fresh copy per class
        cls.__LOAD_HOOKS__ = {}

    @classmethod
    def register_load_hook(cls, typ: Type, func: Callable):
        """Registers the hook for a type, on the default loader by default."""
        cls.__LOAD_HOOKS__[typ] = func

    @classmethod
    def get_load_hook(cls, typ: Type) -> Optional[Callable]:
        """Retrieves the hook for a type, if one exists."""
        return cls.__LOAD_HOOKS__.get(typ)


class BaseDumpHook:
    """
    Container class for type hooks.
    """
    __slots__ = ()

    __DUMP_HOOKS__: ClassVar[Dict[Type, Callable]] = None

    def __init_subclass__(cls):
        super().__init_subclass__()
        # (Re)assign the dict object so we have a fresh copy per class
        cls.__DUMP_HOOKS__ = {}

    @classmethod
    def register_dump_hook(cls, typ: Type, func: Callable):
        """Registers the hook for a type, on the default dumper by default."""
        cls.__DUMP_HOOKS__[typ] = func

    @classmethod
    def get_dump_hook(cls, typ: Type) -> Optional[Callable]:
        """Retrieves the hook for a type, if one exists."""
        return cls.__DUMP_HOOKS__.get(typ)
