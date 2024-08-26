"""
Entry point for the Wizard CLI tool.
"""
import argparse
import os
import platform
import sys
import textwrap
from gettext import gettext as _
from json import JSONDecodeError
from pathlib import Path
from typing import TextIO, Optional

from .schema import PyCodeGenerator
from ..__version__ import __version__


# Define the top-level parser
parser: argparse.ArgumentParser


def main(args=None):
    """
    A companion CLI tool for the Dataclass Wizard, which simplifies
    interaction with the Python `dataclasses` module.
    """

    setup_parser()

    args = parser.parse_args(args)

    try:
        args.func(args)

    except AttributeError:
        # A sub-command is not provided.
        parser.print_help()
        parser.exit(0)


def setup_parser():
    """Sets up the Wizard CLI parser."""
    global parser
    desc = main.__doc__
    py_version = sys.version.split(" ", 1)[0]

    # create the top-level parser
    parser = argparse.ArgumentParser(description=desc)

    # define global flags for the CLI tool
    parser.add_argument('-V', '--version', action='version',
                        version=f'%(prog)s-cli/{__version__} '
                                f'Python/{py_version} '
                                f'{platform.system()}/{platform.release()}',
                        help='Display the version of this tool.')
    # Commenting these out for now, as they are all currently a "no-op".
    # parser.add_argument('-v', '--verbose', action='store_true',
    #                     help='Enable verbose output')
    # parser.add_argument('-q', '--quiet', action='store_true')

    # Add the sub-commands here.

    subparsers = parser.add_subparsers(help='Supported sub-commands')

    # create the parser for the "gs" command
    gs_parser = subparsers.add_parser(
        'gen-schema', aliases=['gs'],
        help='Generates a Python dataclass schema, given a JSON input.')

    gs_parser.add_argument('in_file', metavar='in-file',
                           nargs='?',
                           type=FileTypeWithExt('r', ext='.json'),
                           help="Path to JSON file. The default assumes the "
                                "input is piped from stdin or '-'",
                           default=sys.stdin)

    gs_parser.add_argument('out_file', metavar='out-file',
                           nargs='?',
                           type=FileTypeWithExt('w', ext='.py'),
                           help="Path to new Python file. The default is to "
                                "print the output to stdout or '-'",
                           default=sys.stdout)

    gs_parser.add_argument("-n", "--no-json-file", action="store_true",
                           help='Do not create a separate JSON file. Note '
                                'this only applies when the JSON input is '
                                'piped in to stdin.')

    gs_parser.add_argument("-f", "--force-strings", action="store_true",
                           help='Force-resolve strings to inferred Python types. '
                                'For example, a string appearing as "TRUE" will '
                                'resolve to a `bool` type, instead of the '
                                'default `Union[bool, str]`.')

    gs_parser.add_argument("-x", "--experimental", action="store_true",
                           help='Enable experimental features via a __future__ '
                                'import, which allows PEP-585 and PEP-604 '
                                'style annotations in Python 3.7+')

    gs_parser.set_defaults(func=gen_py_schema)


class FileTypeWithExt(argparse.FileType):
    """
    Extends :class:`argparse.FileType` to add a default file extension if the
    provided file name is missing one.
    """

    def __init__(self, mode='r', ext=None,
                 bufsize=-1, encoding=None, errors='ignore'):

        super().__init__(mode, bufsize, encoding, errors)
        self._ext = ext

    def __call__(self, string):
        # the special argument "-" means sys.std{in,out}
        if string == '-':
            if 'r' in self._mode:
                return sys.stdin
            elif 'w' in self._mode:  # pragma: no branch
                return sys.stdout
            else:   # pragma: no cover
                msg = _('argument "-" with mode %r') % self._mode
                raise ValueError(msg)

        # all other arguments are used as file names
        ext = os.path.splitext(string)[-1].lower()
        # Add the file extension, if needed
        if not ext and self._ext:
            string += self._ext
        try:
            return open(string, self._mode, self._bufsize, self._encoding,
                        self._errors)
        except OSError as e:
            message = _("can't open '%s': %s")
            raise argparse.ArgumentTypeError(message % (string, e))


def get_div(out_file: TextIO, char='_', line_width=50):
    """
    Returns a formatted line divider to print.
    """
    if out_file.isatty():
        try:
            w = os.get_terminal_size(out_file.fileno()).columns - 2
            if w > 0:
                line_width = w
        except (ValueError, OSError):
            # Perhaps not a real terminal after all
            pass

    return char * line_width


def gen_py_schema(args):
    """
    Entry point for the `wiz gen-schema (gs)` command.
    """

    in_file: TextIO = args.in_file
    out_file: TextIO = args.out_file
    no_json_file: bool = args.no_json_file
    force_strings: bool = args.force_strings
    experimental: bool = args.experimental

    # Currently these arguments are unused
    # verbose, quiet = args.verbose, args.quiet

    # Check if input is piped from stdin.
    is_stdin: bool = in_file.name == '<stdin>'

    # Check if output should be displayed to the terminal.
    is_stdout: bool = out_file.name == '<stdout>'

    # Read in contents of the JSON string, from stdin or a local file.
    json_string: str = in_file.read()

    try:
        code_gen = PyCodeGenerator(file_contents=json_string,
                                   force_strings=force_strings,
                                   experimental=experimental)

    except JSONDecodeError as e:
        msg = str(e).lower()

        if is_stdin and ('double quotes' in msg or 'extra data' in msg):
            # We can provide a more helpful error message in this case.
            msg = """\
            Confirm that double quotes are properly applied. For example, the following syntax is invalid:
                echo "{"key": "value"}" | wiz gs

            Instead, wrap the string with single quotes as shown below:
                echo \'{"key": "value"}\' | wiz gs
            """

            _exit_with_error(out_file, msg=msg)

        _exit_with_error(out_file, e)

    except Exception as e:
        _exit_with_error(out_file, e)

    else:
        print('Successfully generated the Python code for the JSON schema.')
        print(get_div(out_file))
        print()

        if not is_stdout:
            out_path = Path(out_file.name)
            # Only create the JSON file if we are piped the input, and the
            # `--no-json-file / -n` option is not passed in.
            add_json_file: bool = is_stdin and not no_json_file

            print(f'Wrote out the Python Code to:  {out_path.absolute()}')

            if add_json_file:
                json_loc = out_path.with_suffix('.json')
                json_loc.write_text(json_string)
                print(f'Saved the JSON Input to:       {json_loc.absolute()}')

        out_file.write(code_gen.py_code)


def _exit_with_error(out_file: TextIO,
                     e: Optional[Exception] = None,
                     msg: Optional[str] = None,
                     line_width=70,
                     indent='  '):
    """
    Prints the error message from an error `e` or an error message `msg`
    and exits the program.
    """

    msg_header = ('An error{err_cls}was encountered while parsing the JSON '
                  'input:')

    if not msg:
        msg = str(e)

    error_lines = [
        msg_header.format(err_cls=f' ({type(e).__name__}) ' if e else ' '),
        get_div(out_file)
    ]

    error_lines.extend(
        textwrap.wrap(
            textwrap.dedent(msg),
            width=line_width,
            initial_indent=indent,
            subsequent_indent=indent,
            drop_whitespace=False,
            replace_whitespace=False,
        )
    )

    sys.exit('\n'.join(error_lines))


if __name__ == "__main__":
    sys.exit(main())
