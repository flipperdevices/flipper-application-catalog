"""
Ideally should be in the `bases` module, however we'll run into a Circular
Import scenario if we move it there, since the `loaders` and `dumpers` modules
both import directly from `bases`.

"""
from datetime import datetime, date
from typing import Type, Optional, Dict, Union

from .abstractions import AbstractJSONWizard
from .bases import AbstractMeta, M
from .class_helper import (
    _META_INITIALIZER, _META,
    get_outer_class_name, get_class_name, create_new_class,
    json_field_to_dataclass_field, dataclass_field_to_json_field
)
from .decorators import try_with_load
from .dumpers import get_dumper
from .enums import LetterCase, DateTimeTo
from .errors import ParseError
from .loaders import get_loader
from .log import LOG
from .type_def import E
from .utils.type_conv import date_to_timestamp, as_enum


# global flag to determine if debug mode was ever enabled
_debug_was_enabled = False


class BaseJSONWizardMeta(AbstractMeta):
    """
    Superclass definition for the `JSONWizard.Meta` inner class.

    See the implementation of the :class:`AbstractMeta` class for the
    available config that can be set, as well as for descriptions on any
    implemented methods.
    """

    __slots__ = ()

    @classmethod
    def _init_subclass(cls):
        """
        Hook that should ideally be run whenever the `Meta` class is
        sub-classed.

        """
        outer_cls_name = get_outer_class_name(cls, raise_=False)

        # We can retrieve the outer class name using `__qualname__`, but it's
        # not easy to find the class definition itself. The simplest way seems
        # to be to create a new callable (essentially a class method for the
        # outer class) which will later be called by the base enclosing class.
        #
        # Note that this relies on the observation that the
        # `__init_subclass__` method of any inner classes are run before the
        # one for the outer class.
        if outer_cls_name is not None:
            _META_INITIALIZER[outer_cls_name] = cls.bind_to
        else:
            # The `Meta` class is defined as an outer class. Emit a warning
            # here, just so we can ensure awareness of this special case.
            LOG.warning('The %r class is not declared as an Inner Class, so '
                        'these are global settings that will apply to all '
                        'JSONSerializable sub-classes.', get_class_name(cls))

            # Copy over global defaults to the :class:`AbstractMeta`
            for attr in AbstractMeta.fields_to_merge:
                setattr(AbstractMeta, attr, getattr(cls, attr, None))
            if cls.json_key_to_field:
                AbstractMeta.json_key_to_field = cls.json_key_to_field

            # Create a new class of `Type[W]`, and then pass `create=False` so
            # that we don't create new loader / dumper for the class.
            new_cls = create_new_class(cls, (AbstractJSONWizard, ))
            cls.bind_to(new_cls, create=False)

    @classmethod
    def bind_to(cls, dataclass: Type, create=True, is_default=True):

        cls_loader = get_loader(dataclass, create=create)
        cls_dumper = get_dumper(dataclass, create=create)

        if cls.debug_enabled:
            global _debug_was_enabled
            if not _debug_was_enabled:
                _debug_was_enabled = True
                LOG.setLevel('DEBUG')
                LOG.info('DEBUG Mode is enabled')

            # Decorate all hooks so they format more helpful messages
            # on error.
            load_hooks = cls_loader.__LOAD_HOOKS__
            for typ in load_hooks:
                load_hooks[typ] = try_with_load(load_hooks[typ])

        if cls.json_key_to_field:
            add_for_both = cls.json_key_to_field.pop('__all__', None)

            json_field_to_dataclass_field(dataclass).update(
                cls.json_key_to_field
            )

            if add_for_both:
                dataclass_to_json_field = dataclass_field_to_json_field(
                    dataclass)

                # We unfortunately can't use a dict comprehension approach, as
                # we don't know if there are multiple JSON keys mapped to a
                # single dataclass field. So to be safe, we should only set
                # the first JSON key mapped to each dataclass field.
                for json_key, field in cls.json_key_to_field.items():
                    if field not in dataclass_to_json_field:
                        dataclass_to_json_field[field] = json_key

        if cls.marshal_date_time_as:
            enum_val = cls._as_enum_safe('marshal_date_time_as', DateTimeTo)

            if enum_val is DateTimeTo.TIMESTAMP:
                # Update dump hooks for the `datetime` and `date` types
                cls_dumper.dump_with_datetime = lambda o, *_: round(o.timestamp())
                cls_dumper.dump_with_date = lambda o, *_: date_to_timestamp(o)
                cls_dumper.register_dump_hook(
                    datetime, cls_dumper.dump_with_datetime)
                cls_dumper.register_dump_hook(
                    date, cls_dumper.dump_with_date)

            elif enum_val is DateTimeTo.ISO_FORMAT:
                # noop; the default dump hook for `datetime` and `date`
                # already serializes using this approach.
                pass

        if cls.key_transform_with_load:
            cls_loader.transform_json_field = cls._as_enum_safe(
                'key_transform_with_load', LetterCase)

        if cls.key_transform_with_dump:
            cls_dumper.transform_dataclass_field = cls._as_enum_safe(
                'key_transform_with_dump', LetterCase)

        # Finally, if needed, save the meta config for the outer class. This
        # will allow us to access this config as part of the JSON load/dump
        # process if needed.
        if is_default:
            # Check if the dataclass already has a Meta config; if so, we need to
            # copy over special attributes so they don't get overwritten.
            if dataclass in _META:
                _META[dataclass] &= cls
            else:
                _META[dataclass] = cls

    @classmethod
    def _as_enum_safe(cls, name: str, base_type: Type[E]) -> Optional[E]:
        """
        Attempt to return the value for class attribute :attr:`attr_name` as
        a :type:`base_type`.

        :raises ParseError: If we are unable to convert the value of the class
          attribute to an Enum of type `base_type`.
        """
        try:
            return as_enum(getattr(cls, name), base_type)

        except ParseError as e:
            # We run into a parsing error while loading the enum; Add
            # additional info on the Exception object before re-raising it
            e.class_name = get_class_name(cls)
            e.field_name = name
            raise


# noinspection PyPep8Naming
def LoadMeta(*, debug_enabled: bool = False,
             recursive: bool = True,
             raise_on_unknown_json_key: bool = False,
             json_key_to_field: Dict[str, str] = None,
             key_transform: Union[LetterCase, str] = None,
             tag: str = None) -> M:
    """
    Helper function to setup the ``Meta`` Config for the JSON load
    (de-serialization) process, which is intended for use alongside the
    ``fromdict`` helper function.

    For descriptions on what each of these params does, refer to the `Docs`_
    below, or check out the :class:`AbstractMeta` definition (I want to avoid
    duplicating the descriptions for params here).

    Examples::

        >>> LoadMeta(key_transform='CAMEL').bind_to(MyClass)
        >>> fromdict(MyClass, {"myStr": "value"})

    .. _Docs: https://dataclass-wizard.readthedocs.io/en/latest/common_use_cases/meta.html
    """

    # Set meta attributes here.
    base_dict = {
        '__slots__': (),
        'raise_on_unknown_json_key': raise_on_unknown_json_key,
        'key_transform_with_load': key_transform,
        'json_key_to_field': json_key_to_field,
        'debug_enabled': debug_enabled,
        'recursive': recursive,
        'tag': tag,
    }

    # Create a new subclass of :class:`AbstractMeta`
    # noinspection PyTypeChecker
    return type('Meta', (BaseJSONWizardMeta, ), base_dict)


# noinspection PyPep8Naming
def DumpMeta(*, debug_enabled: bool = False,
             recursive: bool = True,
             marshal_date_time_as: Union[DateTimeTo, str] = None,
             key_transform: Union[LetterCase, str] = None,
             tag: str = None,
             skip_defaults: bool = False) -> M:
    """
    Helper function to setup the ``Meta`` Config for the JSON dump
    (serialization) process, which is intended for use alongside the
    ``asdict`` helper function.

    For descriptions on what each of these params does, refer to the `Docs`_
    below, or check out the :class:`AbstractMeta` definition (I want to avoid
    duplicating the descriptions for params here).

    Examples::

        >>> DumpMeta(key_transform='CAMEL').bind_to(MyClass)
        >>> asdict(MyClass, {"myStr": "value"})

    .. _Docs: https://dataclass-wizard.readthedocs.io/en/latest/common_use_cases/meta.html
    """

    # Set meta attributes here.
    base_dict = {
        '__slots__': (),
        'marshal_date_time_as': marshal_date_time_as,
        'key_transform_with_dump': key_transform,
        'skip_defaults': skip_defaults,
        'debug_enabled': debug_enabled,
        'recursive': recursive,
        'tag': tag,
    }

    # Create a new subclass of :class:`AbstractMeta`
    # noinspection PyTypeChecker
    return type('Meta', (BaseJSONWizardMeta, ), base_dict)
