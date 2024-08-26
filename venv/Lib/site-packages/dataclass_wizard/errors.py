import json
from abc import ABC, abstractmethod
from dataclasses import Field, MISSING
from typing import (Any, Type, Dict, Tuple, ClassVar,
                    Optional, Union, Iterable)

from .utils.string_conv import normalize


# added as we can't import from `type_def`, as we run into a circular import.
JSONObject = Dict[str, Any]


class JSONWizardError(ABC, Exception):
    """
    Base error class, for errors raised by this library.
    """

    _TEMPLATE: ClassVar[str]

    @property
    @abstractmethod
    def message(self) -> str:
        """
        Format and return an error message.
        """

    def __str__(self):
        return self.message


class ParseError(JSONWizardError):
    """
    Base error when an error occurs during the JSON load process.
    """

    _TEMPLATE = ('Failure parsing field `{field}` in class `{cls}`. Expected '
                 'a type {ann_type}, got {obj_type}.\n'
                 '  value: {o!r}\n'
                 '  error: {e!s}')

    def __init__(self, base_err: Exception,
                 obj: Any,
                 ann_type: Union[Type, Iterable],
                 _default_class: Optional[type] = None,
                 _field_name: Optional[str] = None,
                 _json_object: Any = None,
                 **kwargs):

        super().__init__()

        self.obj = obj
        self.obj_type = type(obj)
        self.ann_type = ann_type
        self.base_error = base_err
        self.kwargs = kwargs
        self._class_name = None
        self._default_class_name = self.name(_default_class) \
            if _default_class else None
        self._field_name = _field_name
        self._json_object = _json_object

    @property
    def class_name(self) -> Optional[str]:
        return self._class_name or self._default_class_name

    @class_name.setter
    def class_name(self, cls: Optional[Type]):
        if self._class_name is None:
            self._class_name = self.name(cls)

    @property
    def field_name(self) -> Optional[str]:
        return self._field_name

    @field_name.setter
    def field_name(self, name: Optional[str]):
        if self._field_name is None:
            self._field_name = name

    @property
    def json_object(self):
        return self._json_object

    @json_object.setter
    def json_object(self, json_obj):
        if self._json_object is None:
            self._json_object = json_obj

    @staticmethod
    def name(obj) -> str:
        """Return the type or class name of an object"""
        return getattr(obj, '__qualname__', getattr(obj, '__name__', obj))

    @property
    def message(self) -> str:
        msg = self._TEMPLATE.format(
            cls=self.class_name, field=self.field_name,
            e=self.base_error, o=self.obj,
            ann_type=self.name(self.ann_type),
            obj_type=self.name(self.obj_type))

        if self.json_object:
            self.kwargs['json_object'] = json.dumps(self.json_object)

        if self.kwargs:
            sep = '\n  '
            parts = sep.join(f'{k}: {v!r}' for k, v in self.kwargs.items())
            msg = f'{msg}{sep}{parts}'

        return msg


class MissingFields(JSONWizardError):
    """
    Error raised when unable to create a class instance (most likely due to
    missing arguments)
    """

    _TEMPLATE = ('Failure calling constructor method of class `{cls}`. '
                 'Missing values for required dataclass fields.\n'
                 '  have fields: {fields!r}\n'
                 '  missing fields: {missing_fields!r}\n'
                 '  input JSON object: {json_string}\n'
                 '  error: {e!s}')

    def __init__(self, base_err: Exception,
                 obj: JSONObject,
                 cls: Type,
                 cls_kwargs: JSONObject,
                 cls_fields: Tuple[Field], **kwargs):

        super().__init__()

        self.obj = obj
        self.fields = list(cls_kwargs.keys())

        self.missing_fields = [f.name for f in cls_fields
                               if f.name not in self.fields
                               and f.default is MISSING
                               and f.default_factory is MISSING]

        # check if any field names match, and where the key transform could be the cause
        # see https://github.com/rnag/dataclass-wizard/issues/54 for more info

        normalized_json_keys = [normalize(key) for key in obj]
        if next((f for f in self.missing_fields if normalize(f) in normalized_json_keys), None):
            from .enums import LetterCase
            from .loaders import get_loader

            key_transform = get_loader(cls).transform_json_field
            if isinstance(key_transform, LetterCase):
                key_transform = key_transform.value.f

            kwargs['key transform'] = f'{key_transform.__name__}()'
            kwargs['resolution'] = 'For more details, please see https://github.com/rnag/dataclass-wizard/issues/54'

        self.base_error = base_err
        self.kwargs = kwargs
        self.class_name: str = self.name(cls)

    @staticmethod
    def name(obj) -> str:
        """Return the type or class name of an object"""
        return getattr(obj, '__qualname__', getattr(obj, '__name__', obj))

    @property
    def message(self) -> str:
        msg = self._TEMPLATE.format(
            cls=self.class_name,
            json_string=json.dumps(self.obj),
            e=self.base_error,
            fields=self.fields,
            missing_fields=self.missing_fields)

        if self.kwargs:
            sep = '\n  '
            parts = sep.join(f'{k}: {v}' for k, v in self.kwargs.items())
            msg = f'{msg}{sep}{parts}'

        return msg


class UnknownJSONKey(JSONWizardError):
    """
    Error raised when an unknown JSON key is encountered in the JSON load
    process.

    Note that this error class is only raised when the
    `raise_on_unknown_json_key` flag is enabled in the :class:`Meta` class.
    """

    _TEMPLATE = ('A JSON key is missing from the dataclass schema for class `{cls}`.\n'
                 '  unknown key: {json_key!r}\n'
                 '  dataclass fields: {fields!r}\n'
                 '  input JSON object: {json_string}')

    def __init__(self,
                 json_key: str,
                 obj: JSONObject,
                 cls: Type,
                 cls_fields: Tuple[Field], **kwargs):
        super().__init__()

        self.json_key = json_key
        self.obj = obj
        self.fields = [f.name for f in cls_fields]
        self.kwargs = kwargs
        self.class_name: str = self.name(cls)

    @staticmethod
    def name(obj) -> str:
        """Return the type or class name of an object"""
        return getattr(obj, '__qualname__', getattr(obj, '__name__', obj))

    @property
    def message(self) -> str:
        msg = self._TEMPLATE.format(
            cls=self.class_name,
            json_string=json.dumps(self.obj),
            fields=self.fields,
            json_key=self.json_key)

        if self.kwargs:
            sep = '\n  '
            parts = sep.join(f'{k}: {v!r}' for k, v in self.kwargs.items())
            msg = f'{msg}{sep}{parts}'

        return msg


class MissingData(ParseError):
    """
    Error raised when unable to create a class instance, as the JSON object
    is None.
    """

    _TEMPLATE = ('Failure loading class `{cls}`. '
                 'Missing value for field (expected a dict, got None)\n'
                 '  dataclass field: {field!r}\n'
                 '  resolution: annotate the field as '
                 '`Optional[{nested_cls}]` or `{nested_cls} | None`')

    def __init__(self, nested_cls: Type, **kwargs):
        super().__init__(self, None, nested_cls, **kwargs)
        self.nested_class_name: str = self.name(nested_cls)

    @staticmethod
    def name(obj) -> str:
        """Return the type or class name of an object"""
        return getattr(obj, '__qualname__', getattr(obj, '__name__', obj))

    @property
    def message(self) -> str:
        msg = self._TEMPLATE.format(
            cls=self.class_name,
            nested_cls=self.nested_class_name,
            json_string=json.dumps(self.obj),
            field=self.field_name,
            o=self.obj,
        )

        if self.kwargs:
            sep = '\n  '
            parts = sep.join(f'{k}: {v!r}' for k, v in self.kwargs.items())
            msg = f'{msg}{sep}{parts}'

        return msg
