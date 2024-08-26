import json
# noinspection PyProtectedMember
from dataclasses import _create_fn, _set_new_attribute
from typing import Type, List, Union, AnyStr

from .abstractions import AbstractJSONWizard, W
from .bases_meta import BaseJSONWizardMeta
from .class_helper import call_meta_initializer_if_needed
from .decorators import _alias
from .dumpers import asdict
from .loaders import fromdict, fromlist
from .type_def import Decoder, Encoder, JSONObject, ListOfJSONObject


class JSONSerializable(AbstractJSONWizard):
    """
    Mixin class to allow a `dataclass` sub-class to be easily converted
    to and from JSON.

    """
    __slots__ = ()

    class Meta(BaseJSONWizardMeta):
        """
        Inner meta class that can be extended by sub-classes for additional
        customization with the JSON load / dump process.
        """
        __slots__ = ()

        # Class attribute to enable detection of the class type.
        __is_inner_meta__ = True

        def __init_subclass__(cls):
            # Set the `__init_subclass__` method here, so we can ensure it
            # doesn't run for the `JSONSerializable.Meta` class.
            return cls._init_subclass()

    @classmethod
    def from_json(cls: Type[W], string: AnyStr, *,
                  decoder: Decoder = json.loads,
                  **decoder_kwargs) -> Union[W, List[W]]:
        """
        Converts a JSON `string` to an instance of the dataclass, or a list of
        the dataclass instances.
        """
        o = decoder(string, **decoder_kwargs)

        return fromdict(cls, o) if isinstance(o, dict) else fromlist(cls, o)

    @classmethod
    @_alias(fromlist)
    def from_list(cls: Type[W], o: ListOfJSONObject) -> List[W]:
        """
        Converts a Python `list` object to a list of the dataclass instances.
        """
        # alias: fromlist(cls, o)
        ...

    @classmethod
    @_alias(fromdict)
    def from_dict(cls: Type[W], o: JSONObject) -> W:
        """
        Converts a Python `dict` object to an instance of the dataclass.
        """
        # alias: fromdict(cls, o)
        ...

    @_alias(asdict)
    def to_dict(self: W) -> JSONObject:
        """
        Converts the dataclass instance to a Python dictionary object that is
        JSON serializable.
        """
        # alias: asdict(self)
        ...

    def to_json(self: W, *,
                encoder: Encoder = json.dumps,
                **encoder_kwargs) -> AnyStr:
        """
        Converts the dataclass instance to a JSON `string` representation.
        """
        return encoder(asdict(self), **encoder_kwargs)

    @classmethod
    def list_to_json(cls: Type[W],
                     instances: List[W],
                     encoder: Encoder = json.dumps,
                     **encoder_kwargs) -> AnyStr:
        """
        Converts a ``list`` of dataclass instances to a JSON `string`
        representation.
        """
        list_of_dict = [asdict(o, cls=cls) for o in instances]

        return encoder(list_of_dict, **encoder_kwargs)

    # noinspection PyShadowingBuiltins
    def __init_subclass__(cls, str=True):
        """
        Checks for optional settings and flags that may be passed in by the
        sub-class, and calls the Meta initializer when :class:`Meta` is sub-classed.

        :param str: True to add a default `__str__` method to the subclass.
        """
        super().__init_subclass__()
        # Calls the Meta initializer when inner :class:`Meta` is sub-classed.
        call_meta_initializer_if_needed(cls)
        # Add a `__str__` method to the subclass, if needed
        if str:
            _set_new_attribute(cls, '__str__', _str_fn())


def _str_fn():
    """
    Converts the dataclass instance to a *prettified* JSON string
    representation, when the `str()` method is invoked.
    """
    return _create_fn('__str__',
                      ('self', ),
                      ['return self.to_json(indent=2)'])
