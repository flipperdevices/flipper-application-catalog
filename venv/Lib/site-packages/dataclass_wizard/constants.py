import os
import sys


# Library Log Level
LOG_LEVEL = os.getenv('WIZARD_LOG_LEVEL', 'ERROR').upper()

# Current system Python version
_PY_VERSION = sys.version_info[:2]

# Check if currently running Python 3.6
PY36 = _PY_VERSION == (3, 6)

# Check if currently running Python 3.8
PY38 = _PY_VERSION == (3, 8)

# Check if currently running Python 3.8 or higher
PY38_OR_ABOVE = _PY_VERSION >= (3, 8)

# Check if currently running Python 3.9
PY39 = _PY_VERSION == (3, 9)

# Check if currently running Python 3.10 or higher
PY310_OR_ABOVE = _PY_VERSION >= (3, 10)

# The name of the dictionary object that contains `load` hooks for each
# object type. Also used to check if a class is a :class:`BaseLoadHook`
_LOAD_HOOKS = '__LOAD_HOOKS__'

# The name of the dictionary object that contains `dump` hooks for each
# object type. Also used to check if a class is a :class:`BaseDumpHook`
_DUMP_HOOKS = '__DUMP_HOOKS__'

# Attribute name that will be defined for single-arg alias functions and
# methods; mainly for internal use.
SINGLE_ARG_ALIAS = '__SINGLE_ARG_ALIAS__'

# Attribute name that will be defined for identity functions and methods;
# mainly for internal use.
IDENTITY = '__IDENTITY__'

# The dictionary key that identifies the tag field for a class. This is only
# set when the `tag` field or the `auto_assign_tags` flag is enabled in the
# `Meta` config for a dataclass.
#
# Note that this key can also be customized in the `Meta` config for a class,
# via the :attr:`tag_key` field.
TAG = '__tag__'
