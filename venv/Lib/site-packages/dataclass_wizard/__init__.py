"""
Dataclass Wizard
~~~~~~~~~~~~~~~~

Marshal dataclasses to/from JSON and Python dict objects. Support properties
with initial values. Generate a dataclass schema for JSON input.

Sample Usage:

    >>> from dataclasses import dataclass, field
    >>> from datetime import datetime
    >>> from typing import Optional, List
    >>>
    >>> from dataclass_wizard import JSONSerializable, property_wizard
    >>>
    >>>
    >>> @dataclass
    >>> class MyClass(JSONSerializable, metaclass=property_wizard):
    >>>
    >>>     my_str: Optional[str]
    >>>     list_of_int: List[int] = field(default_factory=list)
    >>>     # You can also define this as `my_dt`, however only the annotation
    >>>     # will carry over in that case, since the value is re-declared by
    >>>     # the property below.
    >>>     _my_dt: datetime = datetime(2000, 1, 1)
    >>>
    >>>     @property
    >>>     def my_dt(self):
    >>>     # A sample `getter` which returns the datetime with year set as 2010
    >>>         if self._my_dt is not None:
    >>>             return self._my_dt.replace(year=2010)
    >>>         return self._my_dt
    >>>
    >>>     @my_dt.setter
    >>>     def my_dt(self, new_dt: datetime):
    >>>     # A sample `setter` which sets the inverse (roughly) of the `month` and `day`
    >>>         self._my_dt = new_dt.replace(month=13 - new_dt.month,
    >>>                                      day=30 - new_dt.day)
    >>>
    >>>
    >>> string = '''{"myStr": 42, "listOFInt": [1, "2", 3]}'''
    >>> c = MyClass.from_json(string)
    >>> print(repr(c))
    >>> # prints:
    >>> #   MyClass(
    >>> #       my_str='42',
    >>> #       list_of_int=[1, 2, 3],
    >>> #       my_dt=datetime.datetime(2010, 12, 29, 0, 0)
    >>> #   )
    >>> my_dict = {'My_Str': 'string', 'myDT': '2021-01-20T15:55:30Z'}
    >>> c = MyClass.from_dict(my_dict)
    >>> print(repr(c))
    >>> # prints:
    >>> #   MyClass(
    >>> #       my_str='string',
    >>> #       list_of_int=[],
    >>> #       my_dt=datetime.datetime(2010, 12, 10, 15, 55, 30,
    >>> #                               tzinfo=datetime.timezone.utc)
    >>> #   )
    >>> print(c.to_json())
    >>> # prints:
    >>> #   {"myStr": "string", "listOfInt": [], "myDt": "2010-12-10T15:55:30Z"}

For full documentation and more advanced usage, please see
<https://dataclass-wizard.readthedocs.io>.

:copyright: (c) 2021 by Ritvik Nag.
:license: Apache 2.0, see LICENSE for more details.
"""

__all__ = [
    # Base exports
    'JSONSerializable',
    'JSONWizard',
    'LoadMixin',
    'DumpMixin',
    'property_wizard',
    # Wizard Mixins
    'JSONListWizard',
    'JSONFileWizard',
    'YAMLWizard',
    # Helper serializer functions + meta config
    'fromlist',
    'fromdict',
    'asdict',
    'LoadMeta',
    'DumpMeta',
    # Models
    'json_field',
    'json_key',
    'Container',
    'Pattern',
    'DatePattern',
    'TimePattern',
    'DateTimePattern',
]

import logging

from .bases_meta import LoadMeta, DumpMeta
from .constants import PY36
from .dumpers import DumpMixin, setup_default_dumper, asdict
from .loaders import LoadMixin, setup_default_loader, fromlist, fromdict
from .models import (json_field, json_key, Container,
                     Pattern, DatePattern, TimePattern, DateTimePattern)
from .property_wizard import property_wizard
from .serial_json import JSONSerializable
from .wizard_mixins import JSONListWizard, JSONFileWizard, YAMLWizard


# Set up logging to ``/dev/null`` like a library is supposed to.
# http://docs.python.org/3.3/howto/logging.html#configuring-logging-for-a-library
logging.getLogger('dataclass_wizard').addHandler(logging.NullHandler())

# A handy alias in case it comes in useful to anyone :)
JSONWizard = JSONSerializable

# Setup the default type hooks to use when converting `str` (json) or a Python
# `dict` object to a `dataclass` instance.
setup_default_loader()

# Setup the default type hooks to use when converting `dataclass` instances to
# a JSON `string` or a Python `dict` object.
setup_default_dumper()

if PY36:    # pragma: no cover
    # Python 3.6 requires a backport for `datetime.fromisoformat()`
    # noinspection PyPackageRequirements
    # noinspection PyUnresolvedReferences
    from backports.datetime_fromisoformat import MonkeyPatch
    MonkeyPatch.patch_fromisoformat()
