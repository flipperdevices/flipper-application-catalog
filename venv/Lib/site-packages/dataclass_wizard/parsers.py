__all__ = ['IdentityParser',
           'SingleArgParser',
           'Parser',
           'PatternedDTParser',
           'LiteralParser',
           'UnionParser',
           'OptionalParser',
           'IterableParser',
           'TupleParser',
           'VariadicTupleParser',
           'NamedTupleParser',
           'NamedTupleUntypedParser',
           'MappingParser',
           'DefaultDictParser',
           'TypedDictParser']

from dataclasses import dataclass, InitVar, is_dataclass
from typing import (
    Type, Any, Optional, Tuple, Dict, Iterable, Callable, List
)

from .abstractions import AbstractParser, FieldToParser
from .bases import AbstractMeta
from .class_helper import get_meta, _META
from .constants import TAG
from .errors import ParseError
from .models import _PatternedDT, Extras
from .type_def import (
    FrozenKeys, NoneType, DefFactory,
    T, M, S, DD, LSQ, N, NT
)
from .utils.typing_compat import (
    get_origin, get_args, get_named_tuple_field_types,
    get_keys_for_typed_dict, eval_forward_ref_if_needed)


# Type defs
GetParserType = Callable[[Type[T], Type, Extras], AbstractParser]
TupleOfParsers = Tuple[AbstractParser, ...]


@dataclass
class IdentityParser(AbstractParser):
    __slots__ = ()

    def __call__(self, o: Any) -> T:
        return o


@dataclass
class SingleArgParser(AbstractParser):
    __slots__ = ('hook', )

    hook: Callable[[Any], T]

    # noinspection PyDataclass
    def __post_init__(self, *_):
        if not self.hook:
            self.hook = lambda o: o

    def __call__(self, o: Any) -> T:
        return self.hook(o)


@dataclass
class Parser(AbstractParser):
    __slots__ = ('hook', )

    hook: Callable[[Any, Type[T]], T]

    def __call__(self, o: Any) -> T:
        return self.hook(o, self.base_type)


@dataclass
class LiteralParser(AbstractParser):
    __slots__ = ('value_to_type', )

    base_type: Type[M]

    # noinspection PyDataclass
    def __post_init__(self, *_):
        self.value_to_type = {
            val: type(val) for val in get_args(self.base_type)
        }

    def __call__(self, o: Any):
        """
        Checks for Literal equivalence, as mentioned here:
          https://www.python.org/dev/peps/pep-0586/#equivalence-of-two-literals

        """
        try:
            type_does_not_match = type(o) != self.value_to_type[o]

        except KeyError:
            # No such Literal with the value of `o`
            e = ValueError('Value not in expected Literal values')
            raise ParseError(
                e, o, self.base_type,
                allowed_values=list(self.value_to_type))

        else:
            # The value of `o` is in the ones defined for the Literal, but
            # also confirm the type matches the one defined for the Literal.
            if type_does_not_match:
                expected_val = next(v for v in self.value_to_type if v == o)    # pragma: no branch
                e = TypeError(
                    'Value did not match expected type for the Literal')

                raise ParseError(
                    e, o, self.base_type,
                    have_type=type(o),
                    desired_type=self.value_to_type[o],
                    desired_value=expected_val,
                    allowed_values=list(self.value_to_type))

        return o


@dataclass
class PatternedDTParser(AbstractParser):
    __slots__ = ('hook', )

    base_type: _PatternedDT

    # noinspection PyDataclass
    def __post_init__(self, _cls: Type, extras: Extras, *_):
        if not isinstance(self.base_type, _PatternedDT):
            dt_cls = self.base_type
            self.base_type = extras['pattern']
            self.base_type.cls = dt_cls

        self.hook = self.base_type.get_transform_func()

    def __call__(self, date_string: str):
        try:
            return self.hook(date_string)
        except ValueError as e:
            raise ParseError(
                e, date_string, self.base_type.cls,
                pattern=self.base_type.pattern
            )


@dataclass
class OptionalParser(AbstractParser):
    __slots__ = ('parser', )

    get_parser: InitVar[GetParserType]

    def __post_init__(self, cls: Type,
                      extras: Extras,
                      get_parser: GetParserType):

        self.parser: AbstractParser = get_parser(self.base_type, cls, extras)

    def __contains__(self, item):
        """Check if parser is expected to handle the specified item type."""
        if type(item) is NoneType:
            return True

        return super().__contains__(item)

    def __call__(self, o: Any):
        if o is None:
            return o

        return self.parser(o)


@dataclass
class UnionParser(AbstractParser):
    __slots__ = ('parsers', 'tag_to_parser', 'tag_key')

    base_type: Tuple[Type[T], ...]
    get_parser: InitVar[GetParserType]

    def __post_init__(self, cls: Type,
                      extras: Extras,
                      get_parser: GetParserType):

        # Tag key to search for when a dataclass is in a `Union` with
        # other types.
        config = extras.get('config')
        if config:
            self.tag_key: str = config.tag_key or TAG
            auto_assign_tags = config.auto_assign_tags
        else:
            self.tag_key = TAG
            auto_assign_tags = False

        self.parsers = tuple(
            get_parser(t, cls, extras) for t in self.base_type
            if t is not NoneType)

        self.tag_to_parser = {}
        for t in self.base_type:
            t = eval_forward_ref_if_needed(t, cls)
            if is_dataclass(t):
                meta = get_meta(t)
                tag = meta.tag
                if not tag and (auto_assign_tags or meta.auto_assign_tags):
                    cls_name = t.__name__
                    tag = cls_name
                    # We don't want to mutate the base Meta class here
                    if meta is AbstractMeta:
                        from .bases_meta import BaseJSONWizardMeta
                        cls_dict = {'__slots__': (), 'tag': tag}
                        meta = type(cls_name + 'Meta', (BaseJSONWizardMeta, ), cls_dict)
                        _META[t] = meta
                    else:
                        meta.tag = cls_name
                if tag:
                    # TODO see if we can use a mapping of dataclass type to
                    #   load func (maybe one passed in to __post_init__),
                    #   rather than generating one on the fly like this.
                    self.tag_to_parser[tag] = get_parser(t, cls, extras)

    def __contains__(self, item):
        """Check if parser is expected to handle the specified item type."""
        return type(item) in self.base_type

    def __call__(self, o: Any):
        if o is None:
            return o

        for parser in self.parsers:
            if o in parser:
                return parser(o)

        # Attempt to parse to the desired dataclass type, using the "tag"
        # field in the input dictionary object.
        try:
            tag = o[self.tag_key]
        except (TypeError, KeyError):
            # Invalid type (`o` is not a dictionary object) or no such key.
            pass
        else:
            try:
                return self.tag_to_parser[tag](o)
            except KeyError:
                raise ParseError(
                    TypeError('Object with tag was not in any of Union types'),
                    o, [p.base_type for p in self.parsers],
                    input_tag=tag,
                    tag_key=self.tag_key,
                    valid_tags=list(self.tag_to_parser.keys()))

        raise ParseError(
            TypeError('Object was not in any of Union types'),
            o, [p.base_type for p in self.parsers],
            tag_key=self.tag_key
        )


@dataclass
class IterableParser(AbstractParser):
    """
    Parser for a :class:`list`, :class:`set`, :class:`frozenset`,
    :class:`deque`, or a subclass of either type.
    """
    __slots__ = ('hook',
                 'elem_parser')

    base_type: Type[LSQ]
    hook: Callable[[Iterable, Type[LSQ], AbstractParser], LSQ]
    get_parser: InitVar[GetParserType]

    def __post_init__(self, cls: Type,
                      extras: Extras,
                      get_parser: GetParserType):

        # Get the subscripted element type
        #   ex. `List[str]` -> `str`
        try:
            elem_type, = get_args(self.base_type)
        except ValueError:
            elem_type = Any

        # Base type of the object which is instantiable
        #   ex. `List[str]` -> `list`
        self.base_type = get_origin(self.base_type)

        self.elem_parser = get_parser(elem_type, cls, extras)

    def __call__(self, o: Iterable) -> LSQ:
        """
        Load an object `o` into a new object of type `base_type`.

        See the declaration of :var:`LSQ` for more info.
        """
        try:
            return self.hook(o, self.base_type, self.elem_parser)
        # TODO
        except Exception:
            if not isinstance(o, self.base_type):
                e = TypeError('Incorrect type for field')
                raise ParseError(
                    e, o, self.base_type,
                    desired_type=self.base_type)
            else:
                raise


@dataclass
class TupleParser(AbstractParser):
    """
    Parser for subscripted and un-subscripted :class:`Tuple`'s.

    See :class:`VariadicTupleParser` for the parser that handles the variadic
    form, i.e. ``Tuple[str, ...]``
    """
    __slots__ = ('hook',
                 'elem_parsers',
                 'total_count',
                 'required_count')

    # Base type of the object which is instantiable
    #   ex. `Tuple[bool, int]` -> `tuple`
    base_type: Type[S]
    hook: Callable[[Any, Type[S], TupleOfParsers], S]
    get_parser: InitVar[GetParserType]

    def __post_init__(self, cls: Type,
                      extras: Extras,
                      get_parser: GetParserType):

        # Get the subscripted values
        #   ex. `Tuple[bool, int]` -> (bool, int)
        elem_types = get_args(self.base_type)
        self.base_type = get_origin(self.base_type)
        # A collection with a parser for each type argument
        self.elem_parsers = tuple(get_parser(t, cls, extras)
                                  for t in elem_types)
        # Total count is generally the number of type arguments to `Tuple`, but
        # can be `Infinity` when a `Tuple` appears in its un-subscripted form.
        self.total_count: N = len(self.elem_parsers) or float('inf')
        # Minimum number of *required* type arguments
        #   Check for the count of parsers which don't handle `NoneType` -
        #   this should exclude the parsers for `Optional` or `Union` types
        #   that have `None` in the list of args.
        self.required_count: int = len(tuple(p for p in self.elem_parsers
                                             if None not in p))
        if not self.elem_parsers:
            self.elem_parsers = None

    def __call__(self, o: M) -> M:
        """
        Load an object `o` into a new object of type `base_type` (generally a
        :class:`tuple` or a sub-class of one)
        """
        # Confirm that the number of arguments in `o` matches the count in the
        # typed annotation.
        if not self.required_count <= len(o) <= self.total_count:
            e = TypeError('Wrong number of elements.')
            if self.required_count != self.total_count:
                desired_count = f'{self.required_count} - {self.total_count}'
            else:
                desired_count = self.total_count

            raise ParseError(
                e, o, [p.base_type for p in self.elem_parsers],
                desired_count=desired_count,
                actual_count=len(o))

        return self.hook(o, self.base_type, self.elem_parsers)


@dataclass
class VariadicTupleParser(TupleParser):
    """
    Parser that handles the variadic form of :class:`Tuple`'s,
    i.e. ``Tuple[str, ...]``

    Per `PEP 484`_, only **one** required type is allowed before the
    ``Ellipsis``. That is, ``Tuple[int, ...]`` is valid whereas
    ``Tuple[int, str, ...]`` would be invalid. `See here`_ for more info.

    .. _PEP 484: https://www.python.org/dev/peps/pep-0484/
    .. _See here: https://github.com/python/typing/issues/180

    """
    __slots__ = ('first_elem_parser', )

    def __post_init__(self, cls: Type,
                      extras: Extras,
                      get_parser: GetParserType):

        # Get the subscripted values
        #   ex. `Tuple[str, ...]` -> (str, )
        elem_types = get_args(self.base_type)
        # Base type of the object which is instantiable
        #   ex. `Tuple[bool, int]` -> `tuple`
        self.base_type = get_origin(self.base_type)
        # A one-element tuple containing the parser for the first type
        # argument.
        # Given `Tuple[T, ...]`, we only need a parser for `T`
        self.first_elem_parser: Tuple[AbstractParser]
        self.first_elem_parser = get_parser(elem_types[0], cls, extras),
        # Total count should be `Infinity` here, since the variadic form
        # accepts any number of possible arguments.
        self.total_count: N = float('inf')
        self.required_count = 0

    def __call__(self, o: M) -> M:
        """
        Load an object `o` into a new object of type `base_type` (generally a
        :class:`tuple` or a sub-class of one)
        """
        self.elem_parsers = self.first_elem_parser * len(o)
        return super().__call__(o)


@dataclass
class NamedTupleParser(AbstractParser):
    __slots__ = ('hook',
                 'field_to_parser',
                 'field_parsers')

    base_type: Type[S]
    hook: Callable[
        [Any, Type[NT], Optional[FieldToParser], List[AbstractParser]],
        NT
    ]
    get_parser: InitVar[GetParserType]

    def __post_init__(self, cls: Type,
                      extras: Extras,
                      get_parser: GetParserType):

        # Get the field annotations for the `NamedTuple` type
        type_anns: Dict[str, Type[T]] = get_named_tuple_field_types(
            self.base_type
        )

        self.field_to_parser: Optional[FieldToParser] = {
            f: get_parser(ftype, cls, extras)
            for f, ftype in type_anns.items()
        }

        self.field_parsers = list(self.field_to_parser.values())

    def __call__(self, o: Any):
        """
        Load a dictionary or list to a `NamedTuple` sub-class (or an
        un-annotated `namedtuple`)
        """
        return self.hook(o, self.base_type,
                         self.field_to_parser, self.field_parsers)


@dataclass
class NamedTupleUntypedParser(AbstractParser):
    __slots__ = ('hook',
                 'dict_parser',
                 'list_parser')

    base_type: Type[S]
    hook: Callable[[Any, Type[NT], AbstractParser, AbstractParser], NT]
    get_parser: InitVar[GetParserType]

    def __post_init__(self, cls: Type,
                      extras: Extras,
                      get_parser: GetParserType):

        self.dict_parser = get_parser(dict, cls, extras)
        self.list_parser = get_parser(list, cls, extras)

    def __call__(self, o: Any):
        """
        Load a dictionary or list to a `NamedTuple` sub-class (or an
        un-annotated `namedtuple`)
        """
        return self.hook(o, self.base_type,
                         self.dict_parser, self.list_parser)


@dataclass
class MappingParser(AbstractParser):
    __slots__ = ('hook',
                 'key_parser',
                 'val_parser')

    base_type: Type[M]
    hook: Callable[[Any, Type[M], AbstractParser, AbstractParser], M]
    get_parser: InitVar[GetParserType]

    def __post_init__(self, cls: Type,
                      extras: Extras,
                      get_parser: GetParserType):
        try:
            key_type, val_type = get_args(self.base_type)
        except ValueError:
            key_type = val_type = Any

        # Base type of the object which is instantiable
        #   ex. `Dict[str, Any]` -> `dict`
        self.base_type: Type[M] = get_origin(self.base_type)

        self.key_parser = get_parser(key_type, cls, extras)
        self.val_parser = get_parser(val_type, cls, extras)

    def __call__(self, o: M) -> M:
        return self.hook(o, self.base_type, self.key_parser, self.val_parser)


@dataclass
class DefaultDictParser(MappingParser):
    __slots__ = ('default_factory', )

    # Override the type annotations here
    base_type: Type[DD]
    hook: Callable[
        [Any, Type[DD], DefFactory, AbstractParser, AbstractParser], DD]

    def __post_init__(self, cls: Type,
                      extras: Extras,
                      get_parser: GetParserType):
        super().__post_init__(cls, extras, get_parser)

        # The default factory argument to pass to the `defaultdict` subclass
        self.default_factory: DefFactory = self.val_parser.base_type

    def __call__(self, o: M) -> M:
        return self.hook(o, self.base_type, self.default_factory,
                         self.key_parser, self.val_parser)


@dataclass
class TypedDictParser(AbstractParser):
    __slots__ = ('hook',
                 'key_to_parser',
                 'required_keys',
                 'optional_keys')

    base_type: Type[S]
    hook: Callable[[Any, Type[M], FieldToParser, FrozenKeys, FrozenKeys], M]
    get_parser: InitVar[GetParserType]

    def __post_init__(self, cls: Type,
                      extras: Extras,
                      get_parser: GetParserType):

        self.key_to_parser: FieldToParser = {
            k: get_parser(v, cls, extras)
            for k, v in self.base_type.__annotations__.items()
        }

        self.required_keys, self.optional_keys = get_keys_for_typed_dict(
            self.base_type
        )

    def __call__(self, o: M) -> M:
        try:
            return self.hook(o, self.base_type, self.key_to_parser,
                             self.required_keys, self.optional_keys)

        except KeyError as e:
            e = KeyError(f'Missing required key: {e.args[0]}')
            raise ParseError(e, o, self.base_type)

        except Exception:
            if not isinstance(o, dict):
                e = TypeError('Incorrect type for object')
                raise ParseError(
                    e, o, self.base_type, desired_type=self.base_type)
            else:
                raise
