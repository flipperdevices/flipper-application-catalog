__all__ = ['normalize',
           'to_camel_case',
           'to_pascal_case',
           'to_lisp_case',
           'to_snake_case',
           'repl_or_with_union']

import re
from typing import Iterable, Dict, List


def normalize(string: str) -> str:
    """
    Normalize a string - typically a dataclass field name - for comparison
    purposes.
    """
    return string.replace('-', '').replace('_', '').upper()


def to_camel_case(string: str) -> str:
    """
    Convert a string to Camel Case.

    Examples::

        >>> to_camel_case("device_type")
        'deviceType'

    """
    string = replace_multi_with_single(
        string.replace('-', '_').replace(' ', '_'))

    return string[0].lower() + re.sub(
        r"(?:_)(.)", lambda m: m.group(1).upper(), string[1:])


def to_pascal_case(string):
    """
    Converts a string to Pascal Case (also known as "Upper Camel Case")

    Examples::

        >>> to_pascal_case("device_type")
        'DeviceType'

    """
    string = replace_multi_with_single(
        string.replace('-', '_').replace(' ', '_'))

    return string[0].upper() + re.sub(
        r"(?:_)(.)", lambda m: m.group(1).upper(), string[1:])


def to_lisp_case(string: str) -> str:
    """
    Make a hyphenated, lowercase form from the expression in the string.

    Example::

        >>> to_lisp_case("DeviceType")
        'device-type'

    """
    string = string.replace('_', '-').replace(' ', '-')
    # Short path: the field is already lower-cased, so we don't need to handle
    # for camel or title case.
    if string.islower():
        return replace_multi_with_single(string, '-')

    result = re.sub(
        r'((?!^)(?<!-)[A-Z][a-z]+|(?<=[a-z0-9])[A-Z])', r'-\1', string)

    return replace_multi_with_single(result.lower(), '-')


def to_snake_case(string: str) -> str:
    """
    Make an underscored, lowercase form from the expression in the string.

    Example::

        >>> to_snake_case("DeviceType")
        'device_type'

    """
    string = string.replace('-', '_').replace(' ', '_')
    # Short path: the field is already lower-cased, so we don't need to handle
    # for camel or title case.
    if string.islower():
        return replace_multi_with_single(string)

    result = re.sub(
        r'((?!^)(?<!_)[A-Z][a-z]+|(?<=[a-z0-9])[A-Z])', r'_\1', string)

    return replace_multi_with_single(result.lower())


def replace_multi_with_single(string: str, char='_') -> str:
    """
    Replace multiple consecutive occurrences of `char` with a single one.
    """
    rep = char + char
    while rep in string:
        string = string.replace(rep, char)

    return string


# Note: this is the initial helper function I came up with. This doesn't use
# regex for the string transformation, so it's actually faster than the
# implementation above. However, I do prefer the implementation with regex,
# because its a lot cleaner and more simple than this implementation.
# def to_snake_case_old(string: str):
#     """
#     Make an underscored, lowercase form from the expression in the string.
#     """
#     if len(string) < 2:
#         return string or ''
#
#     string = string.replace('-', '_')
#
#     if string.islower():
#         return replace_multi_with_single(string)
#
#     start_idx = 0
#
#     parts = []
#     for i, c in enumerate(string):
#         c: str
#         if c.isupper():
#             try:
#                 next_lower = string[i + 1].islower()
#             except IndexError:
#                 if string[i - 1].islower():
#                     parts.append(string[start_idx:i])
#                     parts.append(c)
#                 else:
#                     parts.append(string[start_idx:])
#                 break
#             else:
#                 if i == 0:
#                     continue
#
#                 if string[i - 1].islower():
#                     parts.append(string[start_idx:i])
#                     start_idx = i
#
#                 elif next_lower:
#                     parts.append(string[start_idx:i])
#                     start_idx = i
#     else:
#         parts.append(string[start_idx:i + 1])
#
#     result = '_'.join(parts).lower()
#
#     return replace_multi_with_single(result)

# Constants
OPEN_BRACKET = '['
CLOSE_BRACKET = ']'
COMMA = ','
OR = '|'

# Replace any OR (|) characters in a forward-declared annotation (i.e. string)
# with a `typing.Union` declaration. See below article for more info.
#
# https://stackoverflow.com/q/69606986/10237506


def repl_or_with_union(s: str):
    """
    Replace all occurrences of PEP 604- style annotations (i.e. like `X | Y`)
    with the Union type from the `typing` module, i.e. like `Union[X, Y]`.

    This is a recursive function that splits a complex annotation in order to
    traverse and parse it, i.e. one that is declared as follows:

      dict[str | Optional[int], list[list[str] | tuple[int | bool] | None]]
    """
    return _repl_or_with_union_inner(s.replace(' ', ''))


def _repl_or_with_union_inner(s: str):

    # If there is no '|' character in the annotation part, we just return it.
    if OR not in s:
        return s

    # Checking for brackets like `List[int | str]`.
    if OPEN_BRACKET in s:

        # Get any indices of COMMA or OR outside a braced expression.
        indices = _outer_comma_and_pipe_indices(s)

        outer_commas = indices[COMMA]
        outer_pipes = indices[OR]

        # We need to check if there are any commas *outside* a bracketed
        # expression. For example, the following cases are what we're looking
        # for here:
        #     value[test], dict[str | int, tuple[bool, str]]
        #     dict[str | int, str], value[test]
        # But we want to ignore cases like these, where all commas are nested
        # within a bracketed expression:
        #     dict[str | int, Union[int, str]]
        if outer_commas:
            return COMMA.join(
                [_repl_or_with_union_inner(i)
                 for i in _sub_strings(s, outer_commas)])

        # We need to check if there are any pipes *outside* a bracketed
        # expression. For example:
        #     value | dict[str | int, list[int | str]]
        #     dict[str, tuple[int | str]] | value
        # But we want to ignore cases like these, where all pipes are
        # nested within the a bracketed expression:
        #     dict[str | int, list[int | str]]
        if outer_pipes:
            or_parts = [_repl_or_with_union_inner(i)
                        for i in _sub_strings(s, outer_pipes)]

            return f'Union{OPEN_BRACKET}{COMMA.join(or_parts)}{CLOSE_BRACKET}'

        # At this point, we know that the annotation does not have an outer
        # COMMA or PIPE expression. We also know that the following syntax
        # is invalid: `SomeType[str][bool]`. Therefore, knowing this, we can
        # assume there is only one outer start and end brace. For example,
        # like `SomeType[str | int, list[dict[str, int | bool]]]`.

        first_start_bracket = s.index(OPEN_BRACKET)
        last_end_bracket = s.rindex(CLOSE_BRACKET)

        # Replace the value enclosed in the outermost brackets
        bracketed_val = _repl_or_with_union_inner(
            s[first_start_bracket + 1:last_end_bracket])

        start_val = s[:first_start_bracket]
        end_val = s[last_end_bracket + 1:]

        return f'{start_val}{OPEN_BRACKET}{bracketed_val}{CLOSE_BRACKET}{end_val}'

    elif COMMA in s:
        # We are dealing with a string like `int | str, float | None`
        return COMMA.join([_repl_or_with_union_inner(i)
                           for i in s.split(COMMA)])

    # We are dealing with a string like `int | str`
    return f'Union{OPEN_BRACKET}{s.replace(OR, COMMA)}{CLOSE_BRACKET}'


def _sub_strings(s: str, split_indices: Iterable[int]):
    """Split a string on the specified indices, and return the split parts."""
    prev = -1

    for idx in split_indices:
        yield s[prev+1:idx]
        prev = idx

    yield s[prev+1:]


def _outer_comma_and_pipe_indices(s: str) -> Dict[str, List[int]]:
    """Return any indices of ',' and '|' that are outside of braces."""
    indices = {OR: [], COMMA: []}
    brace_dict = {OPEN_BRACKET: 1, CLOSE_BRACKET: -1}
    brace_count = 0

    for i, char in enumerate(s):
        if char in brace_dict:
            brace_count += brace_dict[char]
        elif not brace_count and char in indices:
            indices[char].append(i)

    return indices
