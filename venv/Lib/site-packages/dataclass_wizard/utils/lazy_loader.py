"""
Utility for lazy loading Python modules.

Credits: https://wil.yegelwel.com/lazily-importing-python-modules/
"""
import importlib
import logging
import types


class LazyLoader(types.ModuleType):
    """
    Lazily import a module, mainly to avoid pulling in large dependencies.
    `contrib`, and `ffmpeg` are examples of modules that are large and not always
    needed, and this allows them to only be loaded when they are used.
    """

    def __init__(self, parent_module_globals, name,
                 extra=None, local_name=None, warning=None):

        self._local_name = local_name or name
        self._parent_module_globals = parent_module_globals
        self._extra = extra
        self._warning = warning

        super(LazyLoader, self).__init__(name)

    def _load(self):
        """Load the module and insert it into the parent's globals."""

        # Import the target module and insert it into the parent's namespace
        try:
            module = importlib.import_module(self.__name__)

        except ModuleNotFoundError:
            # The lazy-loaded module is not currently installed.
            msg = f'Unable to import the module `{self._local_name}`'

            if self._extra:
                from ..__version__ import __title__
                msg = f'{msg}. Please run the following command to resolve the issue:\n' \
                      f'  $ pip install {__title__}[{self._extra}]'

            raise ImportError(msg) from None

        self._parent_module_globals[self._local_name] = module

        # Emit a warning if one was specified
        if self._warning:
            logging.warning(self._warning)
            # Make sure to only warn once.
            self._warning = None

        # Update this object's dict so that if someone keeps a reference to the
        #   LazyLoader, lookups are efficient (__getattr__ is only called on lookups
        #   that fail).
        self.__dict__.update(module.__dict__)

        return module

    def __getattr__(self, item):
        module = self._load()
        return getattr(module, item)

    def __dir__(self):
        module = self._load()
        return dir(module)
