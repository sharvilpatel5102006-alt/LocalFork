import math
import statistics
from datetime import datetime, timedelta

MAX_ADVANCE_DAYS = 7
FEE_CUTOFF_HOURS = 24
BLOCK_CUTOFF_MINUTES = 15

PICKUP_FORMAT = "%Y-%m-%dT%H:%M"


def median_prep_minutes(prep_minutes_list):
    """Median prep time across the distinct dishes in an order, rounded up
    so the estimate never undersells how long the order will take."""
    if not prep_minutes_list:
        return 15
    return int(math.ceil(statistics.median(prep_minutes_list)))


def pickup_bounds(prep_minutes, now=None):
    """Earliest and latest pickup datetimes a customer may choose."""
    now = now or datetime.now()
    earliest = now + timedelta(minutes=prep_minutes)
    latest = now + timedelta(days=MAX_ADVANCE_DAYS)
    return earliest, latest


def parse_pickup(date_str, time_str):
    try:
        return datetime.strptime(f"{date_str}T{time_str}", PICKUP_FORMAT)
    except (ValueError, TypeError):
        return None


def format_pickup_input(dt):
    """Split a datetime into the (date, time) strings HTML date/time inputs expect."""
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def to_storage(dt):
    return dt.strftime(PICKUP_FORMAT)


def from_storage(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, PICKUP_FORMAT)
    except ValueError:
        return None


def hours_until(pickup_at, now=None):
    dt = from_storage(pickup_at) if isinstance(pickup_at, str) else pickup_at
    if not dt:
        return None
    now = now or datetime.now()
    return (dt - now).total_seconds() / 3600


def is_due_soon(pickup_at, now=None, within_hours=24):
    h = hours_until(pickup_at, now)
    return h is not None and 0 <= h <= within_hours


def cancellation_status(pickup_at, now=None):
    """Returns 'free', 'fee', or 'blocked' for cancelling an order with this pickup time."""
    h = hours_until(pickup_at, now)
    if h is None:
        return "free"
    minutes = h * 60
    if minutes < BLOCK_CUTOFF_MINUTES:
        return "blocked"
    if h < FEE_CUTOFF_HOURS:
        return "fee"
    return "free"
