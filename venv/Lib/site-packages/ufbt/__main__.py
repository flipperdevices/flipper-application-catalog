#
# Module entry point for uFBT
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

from . import ufbt_cli

if __name__ == "__main__":
    import sys

    sys.exit(ufbt_cli() or 0)
