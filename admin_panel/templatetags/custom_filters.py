from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    try:
        return float(value)*float(arg)
    except (ValueError, TypeError):
        try:
            return int(value)*int(arg)
        except (ValueError, TypeError):
            return 0

@register.filter
def status_color(status):
    color_map = {
        'available': 'success',
        'occupied': 'warning',
        'maintenance': 'danger'
    }
    return color_map.get(status, 'secondary')

@register.filter
def booking_status_color(status):
    color_map = {
        'confirmed': 'success',
        'checked_in': 'primary',
        'checked_out': 'info',
        'awaiting_payment': 'warning',
        'cancelled': 'danger'
    }
    return color_map.get(status, 'secondary')

@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return None
    return dictionary.get(key)