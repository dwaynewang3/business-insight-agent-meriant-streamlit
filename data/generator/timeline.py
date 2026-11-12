"""Small date helpers shared by the generator steps."""

from datetime import date


def next_month(day: date) -> date:
    """First day of the month after `day`."""
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def months_before(month: date, count: int) -> date:
    """First day of the month `count` months before `month`."""
    index = month.year * 12 + month.month - 1 - count
    return date(index // 12, index % 12 + 1, 1)


def month_starts(start: date, end: date) -> list[date]:
    """First day of every month from `start` through `end`."""
    months, current = [], date(start.year, start.month, 1)
    while current <= end:
        months.append(current)
        current = next_month(current)
    return months
