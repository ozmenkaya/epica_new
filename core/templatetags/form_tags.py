from django import template
from django.forms import widgets as dj_widgets
from typing import Any, Dict

register = template.Library()


@register.filter(name="get_item")
def get_item(d: Any, key: Any) -> Any:
    try:
        return d.get(key)
    except Exception:
        return None

@register.filter
def widget_name(bound_field: Any) -> str:
    """Return the widget class name of a bound field."""
    try:
        return bound_field.field.widget.__class__.__name__
    except Exception:
        return ""


@register.filter
def is_checkbox(bound_field: Any) -> bool:
    try:
        return isinstance(bound_field.field.widget, dj_widgets.CheckboxInput)
    except Exception:
        return False


def _bootstrap_class_for(bound_field: Any) -> str:
    w = getattr(bound_field.field, "widget", None)
    if isinstance(w, (dj_widgets.Select, dj_widgets.SelectMultiple)):
        return "form-select"
    if isinstance(w, dj_widgets.CheckboxInput):
        return "form-check-input"
    # Default input/textarea/email/number etc.
    return "form-control"


def _is_text_like(bound_field: Any) -> bool:
    w = getattr(bound_field.field, "widget", None)
    return isinstance(
        w,
        (
            dj_widgets.TextInput,
            dj_widgets.EmailInput,
            dj_widgets.NumberInput,
            dj_widgets.URLInput,
            dj_widgets.PasswordInput,
            dj_widgets.Textarea,
        ),
    )


@register.filter(is_safe=True)
def bootstrapify(bound_field: Any) -> str:
    """Render the field with appropriate Bootstrap class, is-invalid, and placeholder for text-like inputs."""
    try:
        attrs = dict(getattr(bound_field.field, "widget", dj_widgets.Widget()).attrs)
        base_cls = attrs.get("class", "").strip()
        bs_cls = _bootstrap_class_for(bound_field)
        classes = f"{base_cls} {bs_cls}".strip()
        if bound_field.errors:
            classes = f"{classes} is-invalid".strip()
        attrs["class"] = classes
        if _is_text_like(bound_field) and not attrs.get("placeholder"):
            attrs["placeholder"] = bound_field.label
        return bound_field.as_widget(attrs=attrs)
    except Exception:
        return str(bound_field)


@register.inclusion_tag("form/field.html")
def bootstrap_field(field: Any) -> Dict[str, Any]:
    """Render a field with label, control, help, and errors using Bootstrap markup.

    - Checkbox: uses .form-check structure
    - Others: label .form-label + control
    """
    try:
        return {
            "field": field,
            "is_checkbox": isinstance(field.field.widget, dj_widgets.CheckboxInput),
        }
    except Exception:
        return {"field": field, "is_checkbox": False}


@register.filter
def remove_trailing_zeros(value: Any) -> str:
    """Remove trailing zeros from decimal numbers."""
    try:
        from decimal import Decimal
        num = Decimal(str(value))
        # Normalize removes trailing zeros
        normalized = num.normalize()
        # Convert to string, preserving the simplified form
        return str(normalized)
    except Exception:
        return str(value)
