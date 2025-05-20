# Standard modules
from enum import Enum


class SearchFocus(Enum):
    """
    Available search focus

    Attributes:
        WEB: Search the web
        WRITING: Search for writing
    """

    WEB = "internet"
    WRITING = "writing"


class SourceFocus(Enum):
    """
    Available source focus

    Attributes:
        WEB: Search the web
        ACADEMIC: Search academic sources
        SOCIAL: Search social media
    """

    WEB = "web"
    ACADEMIC = "scholar"
    SOCIAL = "social"


class TimeRange(Enum):
    """
    Available time range

    Attributes:
        ALL: Include sources from all time
        TODAY: Include sources from today
        LAST_WEEK: Include sources from the last week
        LAST_MONTH: Include sources from the last month
        LAST_YEAR: Include sources from the last year
    """

    ALL = None
    TODAY = "DAY"
    LAST_WEEK = "WEEK"
    LAST_MONTH = "MONTH"
    LAST_YEAR = "YEAR"
