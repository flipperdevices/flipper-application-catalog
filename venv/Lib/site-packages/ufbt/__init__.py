#
# CLI script entry point for uFBT
# This file is part of uFBT <https://github.com/flipperdevices/flipperzero-ufbt>
# Copyright (C) 2022-2023 Flipper Devices Inc.
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import os
import pathlib
import platform
import sys
import oslex

from .bootstrap import (
    DEFAULT_UFBT_HOME,
    ENV_FILE_NAME,
    bootstrap_cli,
    bootstrap_subcommands,
    get_ufbt_package_version,
)

__version__ = get_ufbt_package_version()


def _load_env_file(env_file):
    """
    Minimalistic implementation of env file parser.
    Only supports lines in format `KEY=VALUE`.
    Ignores comments (lines starting with #) and empty lines.
    """
    if not os.path.exists(env_file):
        return {}
    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            env_vars[key] = value
    return env_vars


def ufbt_cli():
    # load environment variables from .env file in current directory
    try:
        env_vars = _load_env_file(ENV_FILE_NAME)
        if env_vars:
            os.environ.update(env_vars)
    except Exception as e:
        print(f"Failed to load environment variables from {ENV_FILE_NAME}: {e}")
        return 2

    if not os.environ.get("UFBT_HOME"):
        os.environ["UFBT_HOME"] = DEFAULT_UFBT_HOME

    os.environ["UFBT_HOME"] = os.path.abspath(os.environ["UFBT_HOME"])

    # ufbt impl uses UFBT_STATE_DIR internally, not UFBT_HOME
    os.environ["UFBT_STATE_DIR"] = os.environ["UFBT_HOME"]
    if not os.environ.get("FBT_TOOLCHAIN_PATH"):
        # fbtenv.sh appends /toolchain/{PLATFORM} to FBT_TOOLCHAIN_PATH
        os.environ["FBT_TOOLCHAIN_PATH"] = os.environ["UFBT_STATE_DIR"]

    ufbt_state_dir = pathlib.Path(os.environ["UFBT_STATE_DIR"])

    # if any of bootstrap subcommands are in the arguments - call it instead
    # kept for compatibility with old scripts, better use `ufbt-bootstrap` directly
    if any(map(sys.argv.__contains__, bootstrap_subcommands)):
        return bootstrap_cli()

    if not os.path.exists(ufbt_state_dir / "current"):
        bootstrap_cli(["update"])

    if not (
        ufbt_script_root := ufbt_state_dir / "current" / "scripts" / "ufbt"
    ).exists():
        print("SDK is missing scripts distribution!")
        print("You might be trying to use an SDK in an outdated format.")
        print("You can clean up current state with `ufbt clean --purge`.")
        print("Run `ufbt update -h` for more information on SDK installation.")
        return 1

    UFBT_APP_DIR = os.getcwd()

    if platform.system() == "Windows":
        commandline = r'call "%UFBT_STATE_DIR%/current/scripts/toolchain/fbtenv.cmd" env & python '
    else:
        commandline = (
            '. "$UFBT_STATE_DIR/current/scripts/toolchain/fbtenv.sh" && python3 '
        )

    commandline += oslex.join(
        [
            "-m",
            "SCons",
            "-Q",
            "--warn=target-not-built",
            "-C",
            str(ufbt_script_root),
            f"UFBT_APP_DIR={UFBT_APP_DIR}",
            *sys.argv[1:],
        ]
    )

    # print(commandline)
    retcode = os.system(commandline)
    if platform.system() != "Windows":
        # low byte is signal number, high byte is exit code
        retcode = retcode >> 8
    return retcode


if __name__ == "__main__":
    sys.exit(ufbt_cli() or 0)
