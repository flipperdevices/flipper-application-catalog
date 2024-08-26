"""
Generates a Python (dataclass) schema, given a JSON input. The entry point for
this module is the `gen-schema` subcommand.

This JSON to Dataclass conversion tool was inspired by the following projects:

    * https://github.com/mischareitsma/json2dataclass
    * https://github.com/russbiggs/json2dataclass
    * https://github.com/mholt/json-to-go

The parser supports the full JSON spec, so both `list` and `dict` as the
root type are properly handled as expected.

A few important notes on the behavior of JSON parsing:

    * Lists with multiple dictionaries will have all the keys and type
      definitions merged into a single model dataclass, as the dictionary
      objects are considered homogenous in this case.

    * Nested lists within the above structure (e.g. list -> dict -> list)
      should similarly merge all list elements with the list for that same key
      in each sibling `dict` object. For example, assuming the below input::
        ... [{"d1": [1, {"k": "v"}]}, {"d1": [{"k": 2}, {"k2": "v2"}, True]}]
      This should result in a single, merged type definition for "d1"::
        ... List[Union[int, dataclass(k: Union[str, int], k2: str), bool]]

    * Any nested dictionaries within lists will have their Model class name
      generated with the singular form of the key containing the model
      definition -- for example, {"Items":[{"key":"value"}]} will result in a
      model class named `Item`. In the case a dictionary is nested within a
      list, it will have the class name auto-incremented with a common
      prefix -- for example, `Data1`, `Data2`, etc.


The implementation below uses regex code in the `rules.english` module from
the library Python-Inflector (https://github.com/bermi/Python-Inflector).

This library is available under the BSD license, which can be
obtained from https://opensource.org/licenses.

The library Python-Inflector contains the following attribution notices:

    Copyright (c) 2006 Bermi Ferrer Martinez
    bermi a-t bermilabs - com

See the end of this file for the original BSD-style license from this library.

"""

__all__ = [
    'PyCodeGenerator'
]

import json
import re
import textwrap
from collections import defaultdict
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field, InitVar
from datetime import date, datetime, time
from enum import Enum
from pathlib import Path
from typing import Callable, Any, Optional, TypeVar, Type, ClassVar
from typing import DefaultDict, Set, List
from typing import (
    Union, Dict, Sequence
)

from .. import property_wizard
from ..class_helper import get_class_name
from ..type_def import PyDeque, JSONList, JSONObject, JSONValue, T
from ..utils.string_conv import to_snake_case, to_pascal_case
# noinspection PyProtectedMember
from ..utils.type_conv import _TRUTHY_VALUES
from ..utils.type_conv import as_datetime, as_date, as_time


# Some unconstrained type variables.  These are used by the container types.
# (These are not for export.)
_S = TypeVar('_S')

# Merge both the "truthy" and "falsy" values, so we can determine the criteria
# under which a string can be considered as a boolean value.
_FALSY_VALUES = ('FALSE', 'F', 'NO', 'N', '0')
_BOOL_VALUES = _TRUTHY_VALUES + _FALSY_VALUES

# Valid types for JSON contents; this can be either a list of any type,
# or a dictionary with `string` keys and values of any type.
JSONBlobType = Union[JSONList, JSONObject]

PyDataTypeOrSeq = Union['PyDataType', Sequence['PyDataType']]
TypeContainerElements = Union[PyDataTypeOrSeq,
                              'PyDataclassGenerator', 'PyListGenerator']


@dataclass
class PyCodeGenerator:
    """
    This is the main class responsible for generating Python code that
    leverages dataclasses, given a JSON object as an input data.
    """

    # Either the file name (ex. file1.json) or the file contents as a string
    # can be passed in as an input to the constructor method.
    file_name: InitVar[str] = None
    file_contents: InitVar[str] = None

    # Should we force-resolve inferred types for strings? For example, a value
    # of "TRUE" will appear as a `Union[str, bool]` type by default.
    force_strings: InitVar[bool] = None

    # Enable experimental features via a `__future__` import, which allows
    # PEP-585 and PEP-604 style annotations in Python 3.7+
    experimental: InitVar[bool] = None

    # The rest of these fields are just for internal use.
    parser: 'JSONRootParser' = field(init=False)
    data: JSONBlobType = field(init=False)
    _py_code_lines: List[str] = field(default=None, init=False)

    def __post_init__(self, file_name: str, file_contents: str,
                      force_strings: bool, experimental: bool):

        # Set global flags
        global Globals
        Globals = _Globals(force_strings=force_strings,
                           experimental=experimental)

        # https://stackoverflow.com/a/62940588/10237506
        if file_name:
            file_path = Path(file_name)
            file_contents = file_path.read_bytes()

        self.data = json.loads(file_contents)
        self.parser = JSONRootParser(self.data)

    @property
    def py_code(self) -> str:

        if self._py_code_lines is None:
            # Generate Python code for the dataclass(es)
            dataclass_code: str = repr(self.parser)
            # Add any imports used at the top of the code
            self._py_code_lines = ModuleImporter.imports
            if self._py_code_lines:
                self._py_code_lines.append('')
            # Generate final Python code - imports + dataclass(es)
            self._py_code_lines.append(dataclass_code)

        return '\n'.join(self._py_code_lines)


# Global flags (generally passed in via command-line) which are shared by
# classes and functions.
#
# Note: unfortunately we can't annotate it as below, because Python 3.6
# complains.
#   Globals: '_Globals' = None
Globals = None


@dataclass
class _Globals:

    # Should we force-resolve inferred types for strings? For example, a value
    # of "TRUE" will appear as a `Union[str, bool]` type by default.
    force_strings: bool = False

    # Enable experimental features via a `__future__` import, which allows
    # PEP-585 and PEP-604 style annotations in Python 3.7+
    experimental: bool = False

    # Should we insert auto-generated comments under each dataclass.
    insert_comments: bool = True

    # Should we include a newline after the comments block mentioned above.
    newline_after_class_def: bool = True


# Credits: https://github.com/bermi/Python-Inflector
class English:
    """
    Inflector for pluralize and singularize English nouns.

    This is the default Inflector for the Inflector obj
    """

    @staticmethod
    def humanize(word):
        """
        Returns a human-readable string from word, by replacing
        underscores with a space, and by upper-casing the initial
        character by default.
        """
        return to_snake_case(word).replace('_', ' ').title()

    @staticmethod
    def singularize(word):
        """Singularizes English nouns."""

        rules = [
            ['(?i)(quiz)zes$', '\\1'],
            ['(?i)(matr)ices$', '\\1ix'],
            ['(?i)(vert|ind)ices$', '\\1ex'],
            ['(?i)^(ox)en', '\\1'],
            ['(?i)(alias|status)es$', '\\1'],
            ['(?i)([octop|vir])i$', '\\1us'],
            ['(?i)(cris|ax|test)es$', '\\1is'],
            ['(?i)(shoe)s$', '\\1'],
            ['(?i)(o)es$', '\\1'],
            ['(?i)(bus)es$', '\\1'],
            ['(?i)([m|l])ice$', '\\1ouse'],
            ['(?i)(x|ch|ss|sh)es$', '\\1'],
            ['(?i)(m)ovies$', '\\1ovie'],
            ['(?i)(s)eries$', '\\1eries'],
            ['(?i)([^aeiouy]|qu)ies$', '\\1y'],
            ['(?i)([lr])ves$', '\\1f'],
            ['(?i)(tive)s$', '\\1'],
            ['(?i)(hive)s$', '\\1'],
            ['(?i)([^f])ves$', '\\1fe'],
            ['(?i)(^analy)ses$', '\\1sis'],
            ['(?i)(^analysis)$', '\\1'],
            ['(?i)((a)naly|(b)a|(d)iagno|(p)arenthe|(p)rogno|(s)ynop|(t)he)ses$', '\\1\\2sis'],
            # I don't want 'Data' replaced with 'Datum', however
            ['(?i)(^data)$', '\\1'],
            ['(?i)([ti])a$', '\\1um'],
            ['(?i)(n)ews$', '\\1ews'],
            ['(?i)s$', ''],
        ]

        uncountable_words = ['equipment', 'information', 'rice', 'money',
                             'species', 'series', 'fish', 'sheep', 'sms']

        irregular_words = {
            'people': 'person',
            'men': 'man',
            'children': 'child',
            'sexes': 'sex',
            'moves': 'move'
        }

        lower_cased_word = word.lower()

        for uncountable_word in uncountable_words:
            if lower_cased_word[-1 * len(uncountable_word):] == uncountable_word:
                return word

        for irregular in irregular_words.keys():
            match = re.search('(' + irregular + ')$', word, re.IGNORECASE)
            if match:
                return re.sub(
                    '(?i)' + irregular + '$',
                    match.expand('\\1')[0] + irregular_words[irregular][1:],
                    word)

        for rule in range(len(rules)):
            match = re.search(rules[rule][0], word, re.IGNORECASE)
            if match:
                groups = match.groups()
                for k in range(0, len(groups)):
                    if groups[k] == None:
                        rules[rule][1] = rules[
                            rule][1].replace('\\' + str(k + 1), '')

                return re.sub(rules[rule][0], rules[rule][1], word)

        return word


# noinspection SpellCheckingInspection, PyPep8Naming
class classproperty:
    """
    Decorator that converts a method with a single cls argument into a
    property that can be accessed directly from the class.

    Credits:
        - https://stackoverflow.com/a/57055258/10237506
        - https://docs.djangoproject.com/en/3.1/ref/utils/#django.utils.functional.classproperty

    """
    def __init__(self, method: Callable[[Any], T]) -> None:
        self.f = method

    def __get__(
            self, instance: Optional[_S], cls: Optional[Type[_S]] = None) -> T:
        return self.f(cls)

    def getter(self, method):
        self.f = method
        return self


def is_float(s: str) -> bool:
    """
    Check if a string is a :class:`float` value
      ex. '1.23'
    """
    try:
        _ = float(s)
        return True
    except ValueError:
        return False


def can_be_bool(o: str) -> bool:
    """
    Check if a string can be a :class:`bool` value. Note this doesn't mean
    that the string can or should be converted to bool, only that it *appears*
    to be one.

    """
    return o.upper() in _BOOL_VALUES


class PyDataType(Enum):
    """
    Enum representing a Python Data Type
    """
    STRING = str
    FLOAT = float
    INT = int
    BOOL = bool
    LIST = list
    DICT = dict
    DATE = date
    DATETIME = datetime
    TIME = time
    NULL = None

    def __str__(self) -> str:
        """
        Returns the string representation of an Enum member's value.
        """
        return getattr(
            self.value, '__name__', str(self.value))


class ModuleImporter:
    """
    Helper class responsible for constructing import statements in the
    generated Python code.
    """

    # Import level (e.g. stdlib or 3rd party) -> Module Name -> Module Imports
    _MOD_IMPORTS: DefaultDict[int, DefaultDict[str, Set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )

    # noinspection PyMethodParameters
    @classproperty
    def imports(cls: Type[T]) -> List[str]:
        """
        Returns a list of generated import statements based on the modules
        currently used in the code.
        """

        lines = []

        for lvl in sorted(cls._MOD_IMPORTS):
            modules = cls._MOD_IMPORTS[lvl]
            for mod in sorted(modules):
                imported = sorted(modules[mod])
                lines.append(f'from {mod} import {", ".join(imported)}')
            lines.append('')

        return lines

    @classmethod
    def wrap_string_with_import(cls, string: str,
                                imported: object,
                                wrap_chars='[]',
                                register_import=True,
                                level=1) -> str:
        """
        Wraps `string` so it is contained within `imported`. The `wrap_chars`
        parameter determines the enclosing characters to use -- defaults to
        braces by default, as subscripted type Generics often appear in this
        form.

        If `register_import` is true (default), an import statement will also
        be generated for the `imported` usage, if one needs to be added.

        Examples::

            >>> ModuleImporter.wrap_string_with_import('int', List)
            'List[int]'

        """

        module = imported.__module__
        name = cls._get_import_name(imported)
        start, end = wrap_chars

        if register_import:
            cls.register_import_by_name(module, name, level)

        return f'{name}{start}{string}{end}'

    # noinspection PyUnresolvedReferences
    @classmethod
    def wrap_with_import(cls, deck: PyDeque[str],
                         imported: object,
                         wrap_chars='[]',
                         register_import=True,
                         level=1) -> None:
        """
        Same as :meth:`wrap_string_with_import` above, except this accepts
        a list (deque) of strings to be wrapped instead.
        """

        module = imported.__module__
        name = cls._get_import_name(imported)
        start, end = wrap_chars

        if register_import:
            cls.register_import_by_name(module, name, level)

        deck.appendleft(start)
        deck.appendleft(name)
        deck.append(end)

    @classmethod
    def register_import(cls, imported: object, level=1) -> None:
        """
        Registers a new import for the given object.

        Examples::

            >>> ModuleImporter.register_import(datetime)

        """

        module = imported.__module__
        name = cls._get_import_name(imported)

        cls.register_import_by_name(module, name, level)

    @classmethod
    def register_import_by_name(cls, module: str, name: str, level: int) -> None:
        """
        Registers a new import for a module and the imported name.

        Note: any built-in's like "int" or "min" should be skipped by
        default.
        """

        # Skip any built-in helper functions
        #   if name in __builtins__.__dict__:
        if module == 'builtins':
            return

        cls._MOD_IMPORTS[level][module].add(name)

    @classmethod
    def register_future_import(cls, name: str) -> None:
        """
        Registers a top-level `__future__` import for a module, which is
        required to be the first import defined at the top of the file.

        """
        cls._MOD_IMPORTS[0]['__future__'].add(name)

    @classmethod
    def clear_imports(cls):
        """
        Clears all the module imports currently in the cache.
        """

        cls._MOD_IMPORTS.clear()

    @classmethod
    def _get_import_name(cls, imported: Any) -> str:
        """Retrieves the name of an imported object."""
        return cls._safe_get_class_name(imported)

    @staticmethod
    def _safe_get_class_name(cls: Any):
        """
        Retrieves the class name of the specified object or class.

        Note: the `_name` attribute is specific to most Generic types in
        the `typing` module.
        """

        try:
            return cls._name

        except AttributeError:
            # Useful to strip underscores from the start, for example
            # in Python 3.6 which doesn't have a `_name` attribute for the
            # `Union` type, and the class name is returned as `_Union`.
            return get_class_name(cls).lstrip('_')


@dataclass(repr=False)
class TypeContainer(List[TypeContainerElements]):
    """
    Custom list class which functions as a container for Python data types.
    """

    # This keeps track of whether we've seen a `null` type before.
    is_optional = False

    def append(self, o: TypeContainerElements):
        """
        Appends an object (or a sequence of objects) to the
        :class:`TypeContainer` instance.
        """

        if isinstance(o, Iterable):
            for elem in o:
                self.append(elem)
            return

        if o is PyDataType.NULL:
            self.is_optional = True
            return

        if o in self:
            return

        if isinstance(o, PyDataType):
            # Register the types in case they are not standard imports.
            # For example, `uuid` and `datetime` objects.
            ModuleImporter.register_import(o.value)

        super(TypeContainer, self).append(o)

    def __or__(self, other):
        """
        Performs logical OR, to merge instances of :class:`TypeContainer`
        """

        if not isinstance(other, TypeContainer):
            raise TypeError(
                f'TypeContainer: incorrect type for __add__: {type(other)}')

        # Remember to carry over the `is_optional` flag
        self.is_optional |= other.is_optional

        if len(self) == 1 and len(other) == 1:
            self_item = self[0]
            other_item = other[0]

            for typ in PyDataclassGenerator, PyListGenerator:
                if isinstance(self_item, typ) and isinstance(other_item, typ):
                    # We call  `__or__` to merge the lists or dataclasses
                    # together.
                    self_item |= other_item

                    return self

        for elem in other:
            self.append(elem)

        return self

    def __repr__(self):
        """
        Iteratively calls the `repr` method of all our model collection types.
        """

        lines = []

        for typ in self:
            if isinstance(typ, (PyDataclassGenerator, PyListGenerator)):
                lines.append(repr(typ))

        return '\n'.join(lines)

    def __str__(self):
        ...

    def _default_str(self):
        """
        Return the string representation of the resolved type -
          ex.`Optional[Union[str, int]]`

        """

        # I'm using `deque`s here to avoid doing `list.insert(0, x)` or later
        # iterating over `reversed(list)`, as this might be a bit faster.
        # noinspection PyUnresolvedReferences
        typing_imports: PyDeque[object] = deque()
        # noinspection PyUnresolvedReferences
        parts: PyDeque[str]

        if not self:
            # This is the case when the only value encountered for a field is
            # a `null` - hence, we're unable to determine the type.
            typing_imports.appendleft(Any)

        elif self.is_optional:
            typing_imports.appendleft(Optional)

        if len(self) > 1:
            # Else, if we have more than one type for a field, then the
            # resolved type should be a `Union` of all the seen types.
            typing_imports.appendleft(Union)

        parts = deque(', '.join(str(typ) for typ in self))

        for tp in typing_imports:
            ModuleImporter.wrap_with_import(parts, tp)

        return ''.join(parts).replace('[]', '')

    def _experimental_features_str(self):

        if not self:
            # This is the case when the only value encountered for a field is
            # a `null` - hence, we're unable to determine the type.
            ModuleImporter.register_import(Any)
            return 'Any'

        parts = [str(typ) for typ in self]
        if self.is_optional:
            parts.append('None')

        return ' | '.join(parts)


def possible_types_for_string_value(string: str) -> PyDataTypeOrSeq:
    """
    Returns possible types for a JSON field with a :class:`string` value,
    depending on what that value appears to be.

    If `Globals.force_strings` is true and there is more than one possible
    type, we simply return the inferred type, instead of the
    `Union[T..., str]` syntax.
    """

    exc_types = TypeError, ValueError

    try:
        _ = as_date(string)
        return PyDataType.DATE
    except exc_types:
        pass

    # I want to eliminate false positives so this seems the easiest
    # way to do that. Otherwise strings like "24" seem to get parsed
    # as a :class:`Time` object, which might not be expected.
    if ':' not in string:
        possible_types = []

        if string.isnumeric():
            possible_types.append(PyDataType.INT)

        elif is_float(string):
            possible_types.append(PyDataType.FLOAT)

        elif can_be_bool(string):
            possible_types.append(PyDataType.BOOL)

        # If force-resolve is enabled, just return the inferred type if one
        # was determined.
        # noinspection PyUnresolvedReferences
        if Globals.force_strings and possible_types:
            return possible_types[0]

        possible_types.append(PyDataType.STRING)

        return possible_types

    try:
        _ = as_time(string)
        return PyDataType.TIME
    except exc_types:
        pass

    try:
        _ = as_datetime(string)
        return PyDataType.DATETIME
    except exc_types:
        pass

    return PyDataType.STRING


def json_to_python_type(o: JSONValue) -> PyDataTypeOrSeq:
    """
    Convert a JSON object to a Python Data Type, or a Union of Python Data
    Types.
    """

    if o is None:
        return PyDataType.NULL

    if isinstance(o, str):
        return possible_types_for_string_value(o)

    # `bool` needs to come before `int`, as it's a subclass of `int`
    if isinstance(o, bool):
        return PyDataType.BOOL

    if isinstance(o, int):
        return PyDataType.INT

    if isinstance(o, float):
        return PyDataType.FLOAT

    if isinstance(o, list):
        return PyDataType.LIST

    if isinstance(o, dict):
        return PyDataType.DICT


@dataclass
class JSONRootParser:

    data: JSONBlobType

    model: Union['PyListGenerator',
                 'PyDataclassGenerator'] = field(init=False)

    def __post_init__(self):

        # Clear imports from last run
        ModuleImporter.clear_imports()

        str_method_prefix = 'default'

        # Check if experimental features are enabled
        if Globals.experimental:
            # Add the required `__future__` import
            ModuleImporter.register_future_import('annotations')
            # Update how annotations are resolved
            str_method_prefix = 'experimental_features'

        # Set the `__str__` method to use for classes
        str_method_name = f'_{str_method_prefix}_str'
        for typ in TypeContainer, PyListGenerator, PyDataclassGenerator:
            typ.__str__ = getattr(typ, str_method_name)

        # We'll need an import for the @dataclass decorator, at a minimum
        ModuleImporter.register_import(dataclass)

        if isinstance(self.data, list):
            self.model = PyListGenerator(self.data,
                                         is_root=True)

        elif isinstance(self.data, dict):
            self.model = PyDataclassGenerator(self.data,
                                              is_root=True)

        else:
            raise TypeError(
                'Incorrect type, expected a JSON `list` or `dict`. '
                f'actual_type={type(self.data)!r}, data={self.data!r}')

    def __repr__(self):
        return repr(self.model) + '\n'


@dataclass
class PyDataclassGenerator(metaclass=property_wizard):

    data: InitVar[JSONObject]

    _name: str = 'data'
    indent: str = ' ' * 4
    is_root: bool = False

    nested_lvl: InitVar[int] = 0

    parsed_types: DefaultDict[str, TypeContainer] = field(
        init=False,
        default_factory=lambda: defaultdict(TypeContainer)
    )

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name: str):
        """Title case the name"""
        self._name = to_pascal_case(name)

    @classmethod
    def load_parsed(
            cls: Type[T],
            parsed_types: Dict[str,
                               Union[PyDataType, 'PyDataclassGenerator']],
            **constructor_kwargs
    ) -> T:

        obj = cls({}, **constructor_kwargs)

        for k, typ in parsed_types.items():
            underscored_field = to_snake_case(k)
            obj.parsed_types[underscored_field].append(typ)

        return obj

    def __post_init__(self, data: JSONObject, nested_lvl: int):

        for k, v in data.items():
            underscored_field = to_snake_case(k)
            typ = json_to_python_type(v)

            if typ is PyDataType.DICT:
                typ = PyDataclassGenerator(
                    v, k,
                    nested_lvl=nested_lvl,
                )
            elif typ is PyDataType.LIST:
                nested_lvl += 1
                typ = PyListGenerator(
                    v, k, k,
                    nested_lvl=nested_lvl,
                )

            self.parsed_types[underscored_field].append(typ)

    def __or__(self, other):
        if not isinstance(other, PyDataclassGenerator):
            raise TypeError(
                f'{self.__class__.__name__}: Incorrect type for `__or__`. '
                f'actual_type: {type(other)}, object={other}')

        for k, v in other.parsed_types.items():
            if k in self.parsed_types:
                self.parsed_types[k] |= v

            else:
                self.parsed_types[k] = v

        return self

    def get_lines(self) -> List[str]:
        if self.is_root:
            ModuleImporter.register_import_by_name(
                'dataclass_wizard', 'JSONWizard', level=2)
            class_name = f'class {self.name}(JSONWizard):'
        else:
            class_name = f'class {self.name}:'

        class_parts = ['@dataclass',
                       class_name]
        parts = []
        nested_parts = []

        # noinspection PyUnresolvedReferences
        if Globals.insert_comments:
            class_parts.append(
                textwrap.indent('"""', self.indent))
            class_parts.append(
                textwrap.indent(f'{self.name} dataclass', self.indent))

            # noinspection PyUnresolvedReferences
            if Globals.newline_after_class_def:
                class_parts.append('')

            class_parts.append(textwrap.indent(
                '"""', self.indent))

        for k, v in self.parsed_types.items():
            line = f'{k}: {v}'
            wrapped_line = textwrap.indent(line, self.indent)
            parts.append(wrapped_line)

            nested_part = repr(v)
            if nested_part:
                nested_parts.append(nested_part)

        for part in nested_parts:
            parts.append('\n')
            parts.append(part)

        if not parts:
            parts = [textwrap.indent('pass', self.indent)]

        class_parts.extend(parts)

        return class_parts

    def __str__(self):
        ...

    def _default_str(self):
        return f"'{self.name}'"

    def _experimental_features_str(self):
        return self.name

    def __repr__(self):
        """
        Returns the Python `dataclasses` representation of the object.
        """
        return '\n'.join(self.get_lines())


@dataclass(repr=False)
class PyListGenerator(metaclass=property_wizard):
    """
    Parse a list in a JSON object to a Python list, based on the following
    rules:

    * If the JSON list contains *only* simple types, for example int,
      str, or bool, then invoking ``str()`` on this object should return
      a Union representation of those types, for example
      `Union[int, str, bool]`.

    * If the JSON list contains *any* complex type, like a dict, then
      all `dict`s should have their keys and values merged together.
      Optional and Union should be included if needed.

      Additionally, if `is_root` is true, then calling ``str()`` will
      effectively ignore any simple types,

    """

    # Default name for model class if none is provided.
    default_name: ClassVar[str] = 'data'

    data: JSONList

    container_name: str = 'container'
    _name: str = None

    indent: str = ' ' * 4

    is_root: InitVar[bool] = False
    nested_lvl: InitVar[int] = 0

    root: PyDataclassGenerator = field(init=False, default=None)

    parsed_types: TypeContainer = field(init=False,
                                        default_factory=TypeContainer)

    # Model is our model dataclass object, which may or may not be present
    # in the list. If there are multiple models (i.e. dicts), their keys
    # and the associated type defs should be merged into one model.
    model: PyDataclassGenerator = field(init=False, default=None)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name: Optional[str]):
        """Title case and singularize the name."""
        if name:
            name = English.humanize(name)
            name = English.singularize(name).replace(' ', '')

        self._name = name

    def __post_init__(self, is_root: bool, nested_lvl: int):

        if not self.name:
            # Increment the suffix if needed
            if nested_lvl:
                self.name = f'{self.default_name}{nested_lvl}'
            else:
                self.name = self.default_name

        # Temp data dictionary object
        data_list = []

        for elem in self.data:

            typ = json_to_python_type(elem)

            if typ is PyDataType.DICT:

                typ = PyDataclassGenerator(elem, self.name,
                                           nested_lvl=nested_lvl,
                                           is_root=is_root)

                if self.model:
                    self.model |= typ
                    continue

                self.model = typ

            else:
                # Nested lists.
                if typ is PyDataType.LIST:
                    nested_lvl += 1
                    typ = PyListGenerator(elem, nested_lvl=nested_lvl)

                data_list.append(typ)

            self.parsed_types.append(typ)

        if is_root:

            # We want to start off by adding the nested `dataclass` field
            # first, so it shows up at the top of the container `dataclass`.
            data_dict = {self.name: self.model} if self.model else {}

            data_dict.update({
                f'field_{i + 1}': elem
                for i, elem in enumerate(data_list)
            })

            self.root = PyDataclassGenerator.load_parsed(
                data_dict,
                nested_lvl=nested_lvl
            )
            self.root.name = self.container_name

    def __or__(self, other):
        """Merge two lists together."""
        if not isinstance(other, PyListGenerator):
            raise TypeError(
                f'{self.__class__.__name__}: Incorrect type for `__or__`. '
                f'actual_type: {type(other)}, object={other}')

        # To merge lists with equal number of elements, that's easy enough:
        #   [{"key": "v1"}] | [{"key2": 2}] = [{"key": "v1", "key2": 2}]
        #
        # But... what happens when it's something like this?
        #   [1, {"key": "v1"}] | [{"key2": "2}, "testing", 1, 2, 3]
        #
        # Solution is to merge the model in the other list class with our
        # model -- note that both ours and the other instance end up with only
        # one model after `__post_init__` runs. However, easiest way is to
        # iterate over the nested types in the other list and check for the
        # model explicitly. For the rest of the types in the other list
        # (including nested lists), we just add them to our current list.
        for t in other.parsed_types:
            if isinstance(t, PyDataclassGenerator):
                if self.model:
                    self.model |= t
                    continue
                self.model = t
            self.parsed_types.append(t)

        return self

    def get_lines(self) -> List[str]:

        lines = []

        if self.root:
            lines.append(repr(self.root))

        else:
            if self.model:
                lines.append(repr(self.model))

            for t in self.parsed_types:
                if isinstance(t, PyListGenerator):
                    code = repr(t)
                    if code:
                        # Only if our list already has a dataclass, append
                        # a newline. This should add the proper number of
                        # spaces, in a case like below.
                        #   [{"another_Key":  "value"}, [{"key":  "value"}]]
                        if self.model:
                            lines.append('\n')
                        lines.append(code)

        return lines

    def __str__(self):
        ...

    def _default_str(self):

        if len(self.parsed_types) == 0:
            # We could also wrap it with 'Optional' here, since we see it's
            # an empty list, but it's probably better to not not do that, as
            # 'Optional' generally means the value can be an explicit "null".
            #
            # return ModuleImporter.wrap_string_with_import('list', Optional)
            return ModuleImporter.wrap_string_with_import('', List)

        return ModuleImporter.wrap_string_with_import(
            str(self.parsed_types), List)

    def _experimental_features_str(self):

        if len(self.parsed_types) == 0:
            return 'list'

        return ModuleImporter.wrap_string_with_import(
            str(self.parsed_types), list)

    def __repr__(self):
        """
        Returns the Python `dataclasses` representation of the object.
        """
        return '\n'.join(self.get_lines())


if __name__ == '__main__':
    loader = PyCodeGenerator('../../tests/testdata/test1.json')
    print(loader.py_code)


# Copyright (c) 2006 Bermi Ferrer Martinez
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software to deal in this software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of this software, and to permit
# persons to whom this software is furnished to do so, subject to the following
# condition:
#
# THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THIS SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THIS SOFTWARE.
