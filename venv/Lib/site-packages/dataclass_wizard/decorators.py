from functools import wraps
from typing import Any, Dict, Type, Callable, Union, TypeVar, cast

from .constants import SINGLE_ARG_ALIAS, IDENTITY
from .errors import ParseError


T = TypeVar('T')


# noinspection PyPep8Naming
class cached_class_property(object):
    """
    Descriptor decorator implementing a class-level, read-only property,
    which caches the attribute on-demand on the first use.

    Credits: https://stackoverflow.com/a/4037979/10237506
    """
    def __init__(self, func):
        self.__func__ = func
        self.__attr_name__ = func.__name__

    def __get__(self, instance, cls=None):
        """This method is only called the first time, to cache the value."""
        if cls is None:
            cls = type(instance)

        # Build the attribute.
        attr = self.__func__(cls)

        # Cache the value; hide ourselves.
        setattr(cls, self.__attr_name__, attr)

        return attr


class cached_property(object):
    """
    Descriptor decorator implementing an instance-level, read-only property,
    which caches the attribute on-demand on the first use.
    """
    def __init__(self, func):
        self.__func__ = func
        self.__attr_name__ = func.__name__

    def __get__(self, instance, cls=None):
        """This method is only called the first time, to cache the value."""
        # Build the attribute.
        attr = self.__func__(instance)

        # Cache the value; hide ourselves.
        setattr(instance, self.__attr_name__, attr)

        return attr


def try_with_load(load_fn: Callable):
    """Try to call a load hook, catch and re-raise errors as a ParseError.

    Note: this function will be recursively called on all load hooks for a
    dataclass, when `debug_mode` is enabled for the dataclass.

    :param load_fn: The load hook, can be a regular callable, a single-arg
      alias, or an identity function.
    :return: The decorated load hook.
    """
    try:  # Check if it's a single-argument function, ex. float(...)
        single_arg_alias_func = getattr(load_fn, SINGLE_ARG_ALIAS)

    except AttributeError:
        # Check if it's an identity function, ex. lambda o: o
        if hasattr(load_fn, IDENTITY):
            # These are basically do-nothing callables, so we don't need to
            # decorate them.
            return load_fn

        @wraps(load_fn)
        def new_func(o: Any, base_type: Type, *args, **kwargs):
            try:
                return load_fn(o, base_type, *args, **kwargs)

            except ParseError as e:
                # This means that a nested load hook raised an exception.
                # Therefore, to help with debugging we should print the name
                # of the outer load hook and the original object.
                e.kwargs['load_hook'] = load_fn.__name__
                e.obj = o
                # Re-raise the original error
                raise

            except Exception as e:
                raise ParseError(e, o, base_type, load_hook=load_fn.__name__)

        return new_func

    else:
        # fix: avoid re-decoration when DEBUG mode is enabled multiple
        # times (i.e. on more than one class)
        if hasattr(load_fn, '__decorated__'):
            return load_fn

        # If it's a string value, we don't know the name of the load hook
        # function (method) beforehand.
        if isinstance(single_arg_alias_func, str):
            alias = single_arg_alias_func
            f_locals = {}
        else:
            alias = single_arg_alias_func.__name__
            f_locals = {alias: single_arg_alias_func}

        wrapped_fn = f'{try_with_load_with_single_arg.__name__}' \
                     f'(original_fn, {alias}, base_type)'

        setattr(load_fn, '__decorated__', True)
        setattr(load_fn, SINGLE_ARG_ALIAS, wrapped_fn)
        setattr(load_fn, 'f_locals', f_locals)

        return load_fn


def try_with_load_with_single_arg(original_fn: Callable,
                                  single_arg_load_fn: Callable,
                                  base_type: Type):
    """Similar to :func:`try_with_load`, but for single-arg alias functions.

    :param original_fn: The original load hook (function)
    :param single_arg_load_fn: The single-argument load hook
    :param base_type: The annotated (or desired) type
    :return: The decorated load hook.
    """
    @wraps(single_arg_load_fn)
    def new_func(o: Any):
        try:
            return single_arg_load_fn(o)

        except ParseError as e:
            # This means that a nested load hook raised an exception.
            # Therefore, to help with debugging we should print the name
            # of the outer load hook and the original object.
            e.kwargs['load_hook'] = original_fn.__name__
            e.obj = o
            # Re-raise the original error
            raise

        except Exception as e:
            raise ParseError(e, o, base_type, load_hook=original_fn.__name__)

    return new_func


def discard_kwargs(f):

    @wraps(f)
    def new_func(*args, **_kwargs):
        return f(*args)

    return new_func


def _alias(default: Callable) -> Callable[[T], T]:
    """
    Decorator which re-assigns a function `_f` to point to `default` instead.
    Since global function calls in Python are somewhat expensive, this is
    mainly done to reduce a bit of overhead involved in the functions calls.

    For example, consider the below example::

        def f2(o):
            return o

        def f1(o):
            return f2(o)

    Calling function `f1` will incur some additional overhead, as opposed to
    simply calling `f2`.

    Now assume we wrap `f1` with the `_alias` decorator::

        def f2(o):
            return o

        @_alias(f2)
        def f1(o):
            ...

    This will essentially perform the assignment of `f1 = f2`, so calling
    `f1()` in this case has no additional function overhead, as opposed to
    just calling `f2()`.
    """

    def new_func(_f: T) -> T:
        return cast(T, default)

    return new_func


def _single_arg_alias(alias_func: Union[Callable, str] = None):
    """
    Decorator which wraps a function to set the :attr:`SINGLE_ARG_ALIAS` on
    a function `f`, which is an alias function that takes only one argument.
    This is useful mainly so that other functions can access this attribute,
    and can opt to call it instead of function `f`.
    """

    def new_func(f):
        setattr(f, SINGLE_ARG_ALIAS, alias_func)
        return f

    return new_func


def _identity(_f: Callable = None, id: Union[object, str] = None):
    """
    Decorator which wraps a function to set the :attr:`IDENTITY` on a function
    `f`, indicating that this is an identity function that returns its first
    argument. This is useful mainly so that other functions can access this
    attribute, and can opt to call it instead of function `f`.
    """

    def new_func(f):
        setattr(f, IDENTITY, id)
        return f

    return new_func(_f) if _f else new_func


def resolve_alias_func(f: Callable,
                       _locals: Dict = None,
                       raise_=False) -> Callable:
    """
    Resolve the underlying single-arg alias function for `f`, using the
    provided function locals (which will be a dict). If `f` does not have an
    associated alias function, we return `f` itself.

    :raises AttributeError: If `raise_` is true and `f` is not a single-arg
      alias function.
    """

    try:
        single_arg_alias_func = getattr(f, SINGLE_ARG_ALIAS)

    except AttributeError:
        if raise_:
            raise
        return f

    else:
        if isinstance(single_arg_alias_func, str) and _locals is not None:
            try:
                return _locals[single_arg_alias_func]
            except KeyError:
                # This is only the case when debug mode is enabled, so the
                # string will be like 'try_with_load_with_single_arg(...)'
                _locals['original_fn'] = f
                f_locals = getattr(f, 'f_locals', None)
                if f_locals:
                    _locals.update(f_locals)

                return eval(single_arg_alias_func, globals(), _locals)

        return single_arg_alias_func
