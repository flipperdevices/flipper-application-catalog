import json
# noinspection PyProtectedMember
from dataclasses import MISSING, Field, _create_fn
from datetime import date, datetime, time
from typing import (cast, Collection, Callable,
                    Optional, List, Union, Type)

from .bases import META
from .constants import PY310_OR_ABOVE
from .decorators import cached_property
from .type_def import T, DT, Encoder, PyTypedDict, FileEncoder
from .utils.type_conv import as_datetime, as_time, as_date


# Type for a string or a collection of strings.
_STR_COLLECTION = Union[str, Collection[str]]

# A date, time, datetime sub type, or None.
DT_OR_NONE = Optional[DT]


class Extras(PyTypedDict):
    """
    "Extra" config that can be used in the load / dump process.
    """
    config: META
    # noinspection PyTypedDict
    pattern: '_PatternedDT'


def json_key(*keys: str, all=False, dump=True):
    """
    Represents a mapping of one or more JSON key names for a dataclass field.

    This is only in *addition* to the default key transform; for example, a
    JSON key appearing as "myField", "MyField" or "my-field" will already map
    to a dataclass field "my_field" by default (assuming the key transform
    converts to snake case).

    The mapping to each JSON key name is case-sensitive, so passing "myfield"
    will not match a "myField" key in a JSON string or a Python dict object.

    :param keys: A list of one of more JSON keys to associate with the
      dataclass field.
    :param all: True to also associate the reverse mapping, i.e. from
      dataclass field to JSON key. If multiple JSON keys are passed in, it
      uses the first one provided in this case. This mapping is then used when
      `to_dict` or `to_json` is called, instead of the default key transform.
    :param dump: False to skip this field in the serialization process to
      JSON. By default, this field and its value is included.
    """

    return JSON(*keys, all=all, dump=dump)


def json_field(keys: _STR_COLLECTION, *,
               all=False, dump=True,
               default=MISSING, default_factory=MISSING,
               init=True, repr=True,
               hash=None, compare=True, metadata=None):
    """
    This is a helper function that sets the same defaults for keyword
    arguments as the ``dataclasses.field`` function. It can be thought of as
    an alias to ``dataclasses.field(...)``, but one which also represents
    a mapping of one or more JSON key names to a dataclass field.

    This is only in *addition* to the default key transform; for example, a
    JSON key appearing as "myField", "MyField" or "my-field" will already map
    to a dataclass field "my_field" by default (assuming the key transform
    converts to snake case).

    The mapping to each JSON key name is case-sensitive, so passing "myfield"
    will not match a "myField" key in a JSON string or a Python dict object.

    `keys` is a string, or a collection (list, tuple, etc.) of strings. It
    represents one of more JSON keys to associate with the dataclass field.

    When `all` is passed as True (default is False), it will also associate
    the reverse mapping, i.e. from dataclass field to JSON key. If multiple
    JSON keys are passed in, it uses the first one provided in this case.
    This mapping is then used when ``to_dict`` or ``to_json`` is called,
    instead of the default key transform.

    When `dump` is passed as False (default is True), this field will be
    skipped, or excluded, in the serialization process to JSON.
    """

    if default is not MISSING and default_factory is not MISSING:
        raise ValueError('cannot specify both default and default_factory')

    return JSONField(keys, all, dump, default, default_factory, init, repr,
                     hash, compare, metadata)


class JSON:
    """
    Represents one or more mappings of JSON keys.

    See the docs on the :func:`json_key` function for more info.
    """
    __slots__ = ('keys',
                 'all',
                 'dump')

    def __init__(self, *keys: str, all=False, dump=True):
        self.keys = keys
        self.all = all
        self.dump = dump


class JSONField(Field):
    """
    Alias to a :class:`dataclasses.Field`, but one which also represents a
    mapping of one or more JSON key names to a dataclass field.

    See the docs on the :func:`json_field` function for more info.
    """
    __slots__ = ('json', )

    # In Python 3.10, dataclasses adds a new parameter to the :class:`Field`
    # constructor: `kw_only`
    #
    # Ref: https://docs.python.org/3.10/library/dataclasses.html#dataclasses.dataclass
    if PY310_OR_ABOVE:  # pragma: no cover
        def __init__(self, keys: _STR_COLLECTION, all: bool, dump: bool,
                     default, default_factory, init, repr, hash, compare,
                     metadata):

            super().__init__(default, default_factory, init, repr, hash,
                             compare, metadata, False)

            if isinstance(keys, str):
                keys = (keys, )

            self.json = JSON(*keys, all=all, dump=dump)

    else:  # pragma: no cover
        def __init__(self, keys: _STR_COLLECTION, all: bool, dump: bool,
                     default, default_factory, init, repr, hash, compare,
                     metadata):

            super().__init__(default, default_factory, init, repr, hash,
                             compare, metadata)

            if isinstance(keys, str):
                keys = (keys, )

            self.json = JSON(*keys, all=all, dump=dump)


# noinspection PyPep8Naming
def Pattern(pattern: str):
    """
    Represents a pattern (i.e. format string) for a date / time / datetime
    type or subtype. For example, a custom pattern like below::

        %d, %b, %Y %H:%M:%S.%f

    A sample usage of ``Pattern``, using a subclass of :class:`time`::

        time_field: Annotated[List[MyTime], Pattern('%I:%M %p')]

    :param pattern: A format string to be passed in to `datetime.strptime`
    """
    return _PatternedDT(pattern)


class _PatternBase:
    """Base "subscriptable" pattern for date/time/datetime."""
    __slots__ = ()

    def __class_getitem__(cls, pattern: str):
        return _PatternedDT(pattern, cast(DT, cls.__base__))

    __getitem__ = __class_getitem__


class DatePattern(date, _PatternBase):
    """
    An annotated type representing a date pattern (i.e. format string). Upon
    de-serialization, the resolved type will be a :class:`date` instead.

    See the docs on :func:`Pattern` for more info.
    """
    __slots__ = ()


class TimePattern(time, _PatternBase):
    """
    An annotated type representing a time pattern (i.e. format string). Upon
    de-serialization, the resolved type will be a :class:`time` instead.

    See the docs on :func:`Pattern` for more info.
    """
    __slots__ = ()


class DateTimePattern(datetime, _PatternBase):
    """
    An annotated type representing a datetime pattern (i.e. format string). Upon
    de-serialization, the resolved type will be a :class:`datetime` instead.

    See the docs on :func:`Pattern` for more info.
    """
    __slots__ = ()


class _PatternedDT:
    """
    Base class for pattern matching using :meth:`datetime.strptime` when
    loading (de-serializing) a string to a date / time / datetime object.
    """

    # `cls` is the date/time/datetime type or subclass.
    # `pattern` is the format string to pass in to `datetime.strptime`.
    __slots__ = ('cls',
                 'pattern')

    def __init__(self, pattern: str, cls: DT_OR_NONE = None):
        self.cls = cls
        self.pattern = pattern

    def get_transform_func(self) -> Callable[[str], DT]:
        """
        Build an return a load function which takes a `date_string` as an
        argument, and returns a new object of type :attr:`cls`.

        We try to parse the input string to a `cls` object in the following
        order:
            - In case it's an ISO-8601 format string, or a numeric timestamp,
              we first parse with the default load function (ex. as_datetime).
              We parse strings using the builtin :meth:`fromisoformat` method,
              as this is much faster than :meth:`datetime.strptime` - see link
              below for more details.
            - Next, we parse with :meth:`datetime.strptime` by passing in the
              :attr:`pattern` to match against. If the pattern is invalid, the
              method raises a ValueError, which is is re-raised by our
              `Parser` implementation.

        Ref: https://stackoverflow.com/questions/13468126/a-faster-strptime

        :raises ValueError: If the input date string does not match the
          pre-defined pattern.
        """

        cls = self.cls

        # Parse with `fromisoformat` first, because its *much* faster than
        # `datetime.strptime` - see linked article above for more details.
        body_lines = [
            'dt = default_load_func(date_string, cls, raise_=False)',
            'if dt is not None:',
            '  return dt',
            'dt = datetime.strptime(date_string, pattern)',
        ]

        locals_ns = {'datetime': datetime,
                     'pattern': self.pattern,
                     'cls': cls}

        if cls is datetime:
            default_load_func = as_datetime
            body_lines.append('return dt')
        elif cls is date:
            default_load_func = as_date
            body_lines.append('return dt.date()')
        elif cls is time:
            default_load_func = as_time
            # temp fix for Python 3.11+, since `time.fromisoformat` is updated
            # to support more formats, such as "-" and "+" in strings.
            if '-' in self.pattern or '+' in self.pattern:
                body_lines = ['try:',
                              '  return datetime.strptime(date_string, pattern).time()',
                              'except (ValueError, TypeError):',
                              '  dt = default_load_func(date_string, cls, raise_=False)',
                              '  if dt is not None:',
                              '    return dt']
            else:
                body_lines.append('return dt.time()')
        elif issubclass(cls, datetime):
            default_load_func = as_datetime
            locals_ns['datetime'] = cls
            body_lines.append('return dt')
        elif issubclass(cls, date):
            default_load_func = as_date
            body_lines.append('return cls(dt.year, dt.month, dt.day)')
        elif issubclass(cls, time):
            default_load_func = as_time
            # temp fix for Python 3.11+, since `time.fromisoformat` is updated
            # to support more formats, such as "-" and "+" in strings.
            if '-' in self.pattern or '+' in self.pattern:
                body_lines = ['try:',
                              '  dt = datetime.strptime(date_string, pattern).time()',
                              'except (ValueError, TypeError):',
                              '  dt = default_load_func(date_string, cls, raise_=False)',
                              '  if dt is not None:',
                              '    return dt']

            body_lines.append('return cls(dt.hour, dt.minute, dt.second, '
                              'dt.microsecond, fold=dt.fold)')
        else:
            raise TypeError(f'Annotation for `Pattern` is of invalid type '
                            f'({cls}). Expected a type or subtype of: '
                            f'{DT.__constraints__}')

        locals_ns['default_load_func'] = default_load_func

        # TODO This approach unfortunately won't work in Python 3.6. To fix
        #   it, we'll need to pass `globals` instead of `locals` here.
        return _create_fn('pattern_to_dt',
                          ('date_string', ),
                          body_lines,
                          locals=locals_ns,
                          return_type=DT)

    def __repr__(self):
        repr_val = [f'{k}={getattr(self, k)!r}' for k in self.__slots__]
        return f'{self.__class__.__name__}({", ".join(repr_val)})'


class Container(List[T]):
    """Convenience wrapper around a collection of dataclass instances.

    For all intents and purposes, this should behave exactly as a `list`
    object.

    Usage:

        >>> from dataclass_wizard import Container, fromlist
        >>> from dataclasses import make_dataclass
        >>>
        >>> A = make_dataclass('A', [('f1', str), ('f2', int)])
        >>> list_of_a = fromlist(A, [{'f1': 'hello', 'f2': 1}, {'f1': 'world', 'f2': 2}])
        >>> c = Container[A](list_of_a)
        >>> print(c.prettify())

    """

    # TODO: Uncomment once we drop support for Python 3.6
    # __slots__ = ('__dict__',
    #              '__orig_class__')

    @cached_property
    def __model__(self) -> Type[T]:
        """
        Given a declaration like Container[T], this returns the subscripted
        value of the generic type T.
        """
        try:
            # noinspection PyUnresolvedReferences
            return self.__orig_class__.__args__[0]
        except AttributeError:
            cls_name = self.__class__.__qualname__
            msg = (f'A {cls_name} object needs to be instantiated with '
                   f'a generic type T.\n\n'
                   'Example:\n'
                   f'  my_list = {cls_name}[T](...)')

            raise TypeError(msg) from None

    def __str__(self):
        """
        Control the value displayed when ``print(self)`` is called.
        """
        import pprint
        return pprint.pformat(self)

    def prettify(self, encoder: Encoder = json.dumps,
                 ensure_ascii=False,
                 **encoder_kwargs) -> str:
        """
        Convert the list of instances to a *prettified* JSON string.
        """
        return self.to_json(
            indent=2,
            encoder=encoder,
            ensure_ascii=ensure_ascii,
            **encoder_kwargs
        )

    def to_json(self, encoder: Encoder = json.dumps,
                **encoder_kwargs) -> str:
        """
        Convert the list of instances to a JSON string.
        """
        from .dumpers import asdict

        cls = self.__model__
        list_of_dict = [asdict(o, cls=cls) for o in self]

        return encoder(list_of_dict, **encoder_kwargs)

    def to_json_file(self, file: str, mode: str = 'w',
                     encoder: FileEncoder = json.dump,
                     **encoder_kwargs) -> None:
        """
        Serializes the list of instances and writes it to a JSON file.
        """
        from .dumpers import asdict

        cls = self.__model__
        list_of_dict = [asdict(o, cls=cls) for o in self]

        with open(file, mode) as out_file:
            encoder(list_of_dict, out_file, **encoder_kwargs)
