# -*- coding: utf-8 -*-

"""
On windows, before a command line argument becomes a ``char*`` in a
program's argv, it must be parsed by both ``cmd.exe``, and by
``CommandLineToArgvW``.

For some strings there is no way to quote them so they will
parse correctly in both situations.
"""

import sys
import re
import itertools

from typing import Iterator, List, Match, TextIO  # noqa: F401

from .exceptions import MSLexError

__all__ = ("split", "quote", "join", "MSLexError")

__version__ = "1.2.0"


def iter_arg(peek: Match[str], i: Iterator[Match[str]]) -> Iterator[str]:
    quote_mode = False
    for m in itertools.chain([peek], i):
        space, slashes, quotes, text = m.groups()
        if space:
            if quote_mode:
                yield space
            else:
                return
        elif quotes:
            n_slashes = len(slashes)
            n_quotes = len(quotes)
            slashes_odd = bool(n_slashes % 2)
            yield "\\" * (n_slashes // 2)
            magic_sum = n_quotes + quote_mode + 2 * slashes_odd
            yield '"' * (magic_sum // 3)
            quote_mode = (magic_sum % 3) == 1
        else:
            yield text


def iter_args(s: str) -> Iterator[str]:
    i = re.finditer(r"(\s+)|(\\*)(\"+)|(.[^\s\\\"]*)", s.lstrip())
    for m in i:
        yield "".join(iter_arg(m, i))


cmd_meta = r"([\"\^\&\|\<\>\(\)\%\!])"
cmd_meta_or_space = r"[\s\"\^\&\|\<\>\(\)\%\!]"

cmd_meta_inside_quotes = r"([\"\%\!])"


def split(s: str, like_cmd: bool = True, check: bool = True) -> List[str]:
    """
    Split a string of command line arguments like DOS and Windows do.

    :param s: a string to parse
    :param like_cmd: parse it like ``cmd.exe``
    :param check: raise an error on unquoted metacharacters
    :return: a list of parsed words

    If ``like_cmd`` is true, then this will emulate both ``cmd.exe`` and
    ``CommandLineToArgvW``.   Since ``cmd.exe`` is a shell, and can run
    external programs, this function obviously cannot emulate
    everything it does.   However if the string passed in would
    be parsed by cmd as a quoted literal, without command
    invocations like ``&whoami``, and without string substitutions like
    ``%PATH%``, then this function will split it accurately.

    f ``like_cmd`` is false, then this will split the string like
    ``CommandLineToArgvW`` does.

    If ``check`` is true, this will raise a ``ValueError`` if cmd metacharacters
    occur in the string without being quoted.
    """
    if like_cmd and re.search(cmd_meta, s):

        def i() -> Iterator[str]:
            quote_mode = False
            for m in re.finditer(r"(\^.)|(\")|([^\^\"]+)", s):
                escaped, quote, text = m.groups()
                if escaped:
                    if quote_mode:
                        yield escaped
                        if escaped[1] == '"':
                            quote_mode = False
                    else:
                        yield escaped[1]
                elif quote:
                    yield '"'
                    quote_mode = not quote_mode
                else:
                    yield text
                    if check:
                        meta = cmd_meta_inside_quotes if quote_mode else cmd_meta
                        if re.search(meta, text):
                            raise MSLexError("Unquoted CMD metacharacters in string: " + repr(s))

        s = "".join(i())
    return list(iter_args(s))


def quote(s: str, for_cmd: bool = True) -> str:
    """
    Quote a string for use as a command line argument in DOS or Windows.

    :param s: a string to quote
    :param for_cmd: quote it for ``cmd.exe``
    :return: quoted string

    If ``for_cmd`` is true, then this will quote the strings so the result will
    be parsed correctly by ``cmd.exe`` and then by ``CommandLineToArgvW``.   If
    false, then this will quote the strings so the result will
    be parsed correctly when passed directly to ``CommandLineToArgvW``.
    """
    if not s:
        return '""'
    if not re.search(cmd_meta_or_space, s):
        return s
    if for_cmd and re.search(cmd_meta, s):
        if not re.search(cmd_meta_inside_quotes, s):
            m = re.search(r"\\+$", s)
            if m:
                return '"' + s + m.group() + '"'
            else:
                return '"' + s + '"'
        if not re.search(r"[\s\"]", s):
            return re.sub(cmd_meta, r"^\1", s)
        return re.sub(cmd_meta, r"^\1", quote(s, for_cmd=False))
    i = re.finditer(r"(\\*)(\"+)|(\\+)|([^\\\"]+)", s)

    def parts() -> Iterator[str]:
        yield '"'
        for m in i:
            pos, end = m.span()
            slashes, quotes, onlyslashes, text = m.groups()
            if quotes:
                yield slashes
                yield slashes
                yield r"\"" * len(quotes)
            elif onlyslashes:
                if end == len(s):
                    yield onlyslashes
                    yield onlyslashes
                else:
                    yield onlyslashes
            else:
                yield text
        yield '"'

    return "".join(parts())


def join(split_command: List[str], for_cmd: bool = True) -> str:
    """
    Quote and concatenate a list of strings for use as a command line in DOS
    or Windows.

    :param split_command: a list of words to be quoted
    :param for_cmd: quote it for ``cmd.exe``
    :return: quoted command string

    If ``for_cmd`` is true, then this will quote the strings so the result will
    be parsed correctly by ``cmd.exe`` and then by ``CommandLineToArgvW``.   If
    false, then this will quote the strings so the result will
    be parsed correctly when passed directly to ``CommandLineToArgvW``.

    """
    return " ".join(quote(arg, for_cmd) for arg in split_command)


def split_cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="split a file into strings using windows-style quoting "
    )
    parser.add_argument("filename", nargs="?", help="file to split")
    args = parser.parse_args()

    if args.filename:
        input = open(args.filename, "r")  # type: TextIO
    else:
        input = sys.stdin

    for s in iter_args(input.read()):
        print(s)
