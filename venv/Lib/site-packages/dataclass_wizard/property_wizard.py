from dataclasses import MISSING, Field, field as dataclass_field
from functools import wraps
from typing import Dict, Any, Type, Union, Tuple, Optional

from .type_def import T, NoneType
from .utils.typing_compat import (
    get_origin, get_args, is_generic, is_literal, is_annotated, eval_forward_ref_if_needed
)


AnnotationType = Dict[str, Type[T]]
AnnotationReplType = Dict[str, str]


def property_wizard(*args, **kwargs):
    """
    Adds support for field properties with default values in dataclasses.

    For examples of usage, please see the `Using Field Properties`_ section in
    the docs. I also added `an answer`_ on a SO article that deals with using
    such properties in dataclasses.

    .. _Using Field Properties: https://dataclass-wizard.readthedocs.io/en/latest/using_field_properties.html
    .. _an answer: https://stackoverflow.com/a/68488125/10237506
    """

    cls: Type = type(*args, **kwargs)
    cls_dict: Dict[str, Any] = args[2]
    annotations: AnnotationType = cls_dict.get('__annotations__', {})

    # For each property, we want to replace the annotation for the underscore-
    # leading field associated with that property with the 'public' field
    # name, and this mapping helps us keep a track of that.
    annotation_repls: AnnotationReplType = {}

    for f, val in cls_dict.items():

        if isinstance(val, property):

            if val.fset is None:
                # The property is read-only, not settable
                continue

            if not f.startswith('_'):
                # The property is marked as 'public' (i.e. no leading
                # underscore)
                _process_public_property(
                    cls, f, val, annotations, annotation_repls)
            else:
                # The property is marked as 'private'
                _process_underscored_property(
                    cls, f, val, annotations, annotation_repls)

    if annotation_repls:
        # Use a comprehension approach because we want to replace a
        # key while preserving the insertion order, because the order
        # of fields does matter when the constructor is called.
        cls.__annotations__ = {annotation_repls.get(f, f): ftype
                               for f, ftype in cls.__annotations__.items()}

    return cls


def _process_public_property(cls: Type, public_f: str, val: property,
                             annotations: AnnotationType,
                             annotation_repls: AnnotationReplType):
    """
    Handles the case when the property is marked as 'public' (i.e. no leading
    underscore)
    """

    # The field with a leading underscore
    under_f = '_' + public_f

    # The field value that defines either a `default` or `default_factory`
    fval: Field = dataclass_field()

    # This flag is used to keep a track of whether we already have a default
    # value set (either from the public or the underscored field)
    is_set: bool = False

    if public_f not in annotations and under_f not in annotations:
        # adding this to check if it's a regular property (not
        # associated with a dataclass field)
        return

    if under_f in annotations:
        # Also add it to the list of class annotations to replace later
        #   (this is what `dataclasses` uses to add the field to the
        #   constructor)
        annotation_repls[under_f] = public_f

        try:
            # Get the value of the underscored field
            v = getattr(cls, under_f)
        except AttributeError:
            # The underscored field is probably type-annotated but not defined
            #   i.e. my_var: str
            fval = _default_from_annotation(cls, annotations, under_f)
        else:
            # Check if the value of underscored field is a dataclass Field. If
            # so, we can use the `default` or `default_factory` if one is set.
            if isinstance(v, Field):
                fval, is_set = _process_field(cls, annotations, under_f, v)
            else:
                fval.default = v
                is_set = True
            # Delete the field that starts with an underscore. This is needed
            # since we'll be replacing the annotation for `under_f` later, and
            # `dataclasses` will complain if it sees a variable which is a
            # `Field` that appears to be missing a type annotation.
            delattr(cls, under_f)

    if public_f in annotations and not is_set:
        fval = _default_from_annotation(cls, annotations, public_f)

    # Wraps the `setter` for the property
    val = val.setter(_wrapper(val.fset, fval))

    # Set the field that does not start with an underscore
    setattr(cls, public_f, val)


def _process_underscored_property(cls: Type, under_f: str, val: property,
                                  annotations: AnnotationType,
                                  annotation_repls: AnnotationReplType):
    """
    Handles the case when the property is marked as 'private' (i.e. leads with
    an underscore)
    """

    # The field *without* a leading underscore
    public_f = under_f.lstrip('_')

    # The field value that defines either a `default` or `default_factory`
    fval: Field = dataclass_field()

    if public_f not in annotations and under_f not in annotations:
        # adding this to check if it's a regular property (not
        # associated with a dataclass field)
        return

    if under_f in annotations:
        # Also add it to the list of class annotations to replace later
        #   (this is what `dataclasses` uses to add the field to the
        #   constructor)
        annotation_repls[under_f] = public_f
        fval = _default_from_annotation(cls, annotations, under_f)

    if public_f in annotations:
        # First, get the type annotation for the public field
        fval = _default_from_annotation(cls, annotations, public_f)

        if hasattr(cls, public_f):
            # Get the value of the field without a leading underscore
            v = getattr(cls, public_f)
            # Check if the value of public field is a dataclass Field. If so,
            # we can use the `default` or `default_factory` if one is set.
            if isinstance(v, Field):
                fval = _process_field(cls, annotations, public_f, v)[0]
            else:
                fval.default = v

    # Wraps the `setter` for the property
    val = val.setter(_wrapper(val.fset, fval))

    # Replace the value of the field without a leading underscore
    setattr(cls, public_f, val)

    # Delete the property associated with the underscored field name.
    # This is technically not needed, but it supports cases where we
    # define an attribute with the same name as the property, i.e.
    #    @property
    #    def _wheels(self)
    #        return self._wheels
    delattr(cls, under_f)


def _process_field(cls: Type, cls_annotations: AnnotationType,
                   field: str, field_val: Field) -> Tuple[Field, bool]:
    """
    Get the default value for `field`, which is defined as a
    :class:`dataclasses.Field`.

    Returns a two-element tuple of (fval, is_set), where `is_set` will be
    False when no `default` or `default_factory` is defined for the Field;
    in that case, `fval` will be the default value from the annotated type
    instead.
    """

    if field_val.default is not MISSING:
        return field_val, True
    elif field_val.default_factory is not MISSING:
        return field_val, True
    else:
        field_val = _default_from_annotation(cls, cls_annotations, field)
        return field_val, False


def _default_from_annotation(
        cls: Type, cls_annotations: AnnotationType, field: str) -> Field:
    """
    Get the default value for the type annotated on a field. Note that we
    include a check to see if the annotated type is a `Generic` type from the
    ``typing`` module.
    """

    default_type = cls_annotations.get(field)

    try:
        default_type = eval_forward_ref_if_needed(default_type, cls)
    except NameError:
        # Since we are run as a metaclass, we can only evaluate types that are
        # available when the base class `cls` is declared; thus, we can run
        # into an error when the annotation has a forward reference to a class
        # or type that is not yet defined.
        default_type = None

    if is_generic(default_type):
        # Annotated type is a Generic from the `typing` module
        return _default_from_generic_type(cls, default_type, field)

    return _default_from_type(default_type)


def _default_from_type(default_type: Type[T]) -> Field:
    """
    Get the default value for a type. If it's a mutable type, we want to
    use the `default_factory` instead; otherwise, we just use the default
    value from the no-args constructor for the type.
    """

    try:
        # Check if it's callable with no args
        default = default_type()
    except TypeError:
        return dataclass_field()
    else:
        # Check for mutable types, as they need to use a default factory.
        if isinstance(default, (list, dict, set)):
            return dataclass_field(default_factory=default_type)
        # Else, we can just return the default value without a factory.
        return dataclass_field(default=default)


def _default_from_generic_type(
        cls: Type,
        default_type: Type[T],
        field: Optional[str] = None) -> Field:
    """
    Process a Generic type from the `typing` module, and return the default
    value (or default factory) for the annotated type.
    """

    args = get_args(default_type)
    origin = get_origin(default_type)

    if is_annotated(default_type):
        # The Generic type appears as `Annotated[T, extras...]`
        default_type, *extras = args
        # Loop over and search for any `dataclasses.Field` types
        for extra in extras:
            if isinstance(extra, Field):
                return _process_field(
                    cls, {field: default_type}, field, extra)[0]
        # Else, if none of the extras are particularly useful, just process
        # type `T`, which can be either a concrete or Generic sub-type.
        return _default_from_annotation(cls, {field: default_type}, field)

    if is_literal(default_type):
        # The Generic type appears as `Literal["r", "r+", ...]`
        return dataclass_field(default=_default_from_typing_args(args))

    if origin is Union:
        # The Generic type appears as `Optional[T]` or `Union[T1, T2, ...]`
        default_type = _default_from_typing_args(args)
        return _default_from_type(default_type)

    return _default_from_type(origin)


def _default_from_typing_args(args: Optional[Tuple[Type[T], ...]]):
    """
    `args` is the type arguments for a generic annotated type from the
    ``typing`` module. For example, given a generic type `Union[str, int]`,
    the args will be a tuple of (str, int).

    If `None` is included in the typed args for `cls`, then it's perfectly
    valid to return `None` as the default. Otherwise, we'll just use the first
    type in the list of args.

    """

    if args and NoneType not in args:
        try:
            return args[0]
        except TypeError:   # pragma: no cover
            return None
    return None


def _wrapper(fset, fval: Field):
    """
    Wraps the property `setter` method to check if we are passed in a property
    object itself, which will be true when no initial value is specified.

    ``fval`` here is a :class:`dataclasses.Field` that contains either a
    `default` or `default_factory`.
    """

    if fval.default_factory is not MISSING:
        # The initial value for the property is returned from a default
        # factory.
        default_factory = fval.default_factory

        @wraps(fset)
        def new_fset(self, value):
            if isinstance(value, property):
                value = default_factory()
            fset(self, value)

    else:
        # The initial value for the property is just a default value.
        default = None if fval.default is MISSING else fval.default

        @wraps(fset)
        def new_fset(self, value):
            if isinstance(value, property):
                value = default
            fset(self, value)

    return new_fset
