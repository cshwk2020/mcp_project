from datetime import datetime

def safe_datetime(val):
    """
    Convert WooCommerce ISO8601 datetime string to Odoo format '%Y-%m-%d %H:%M:%S'.
    If val is None or invalid, return None.
    """
    if not val:
        return None
    try:
        # WooCommerce: '2026-05-28T18:28:27'
        dt = datetime.fromisoformat(val.replace("Z", "").replace("T", " "))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def safe_dict(d: dict) -> dict:
    """Remove None values from dict before sending to Odoo XML-RPC."""
    return {k: v for k, v in d.items() if v is not None}


def safe_val(val, default=""):
    """Return val if not None, otherwise default."""
    return val if val is not None else default

def safe_str(val, default=""):
    """Convert to string, fallback default if None."""
    return str(val) if val is not None else default

def safe_int(val, default=0):
    """Convert to int, fallback default if None or invalid."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return default

def safe_float(val, default=0.0):
    """Convert to float, fallback default if None or invalid."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default
