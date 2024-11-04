import copy
import datetime
from dataclasses import dataclass
from functools import cached_property
from typing import Literal, Self

import dateutil.parser
from astropy.time import Time

DAYOBS_TZ = datetime.timezone(datetime.timedelta(hours=-12))
MJD_EPOCH = datetime.date(1858, 11, 17)
ONE_DAY = datetime.timedelta(days=1)

IntDateFormat = Literal["mjd", "yyyymmdd", "auto"]


# Use a frozen dataclass so that we can used cached properties without
# having to worry about updating them.
@dataclass(frozen=True)
class DayObs:
    """Represent a day of observation, dayobs, as defined in SITCOMTN-032.
    That is, the date in the -12hr timezone, such that the "date" of an
    entire night of observing is the calendar date in Chile of the evening in
    which the night begins.

    Parameters
    ----------
    date : `datetime.date`
        The calendar date.
    int_format : `str`
        ``yyyymmdd`` if an integer representation is a mapping of decimal
        digits to year, month, and day; ``mjd`` if the integer representation
        is the Modified Julian Date. The default is ``mjd``.
    """

    # Use the standard library date as a lowest common denominator
    # that cannot represent more or less than we want it to.
    date: datetime.date
    int_format: IntDateFormat = "auto"

    @classmethod
    def from_date(cls, arg: datetime.date | int | str | Self, int_format: IntDateFormat = "auto") -> Self:
        """Create a representation of day_obs for a given date.
        This factory takes a representation of the date (already in the
        -12hr timezone as defined in SITCOMTN-032), not a date and time.

        Parameters
        ----------
        arg : `datetime.date` | `int` | `str`
            The representation of dayobs, as defined in SITCOMTN-032.
            If an integer, it will be interpreted according to the
            ``int_format`` argument.
            If it is "yesterday", "today", or "tomorrow", it uses the day_obs
            reletive to the current time.
            A reasonable attempt is made to interpret other strings as
            dates.
        int_format : `str` (optional)
            One of ``mjd``, in which case integers are interpreted as Modified
            Julian Dates,
            ``yyyymmdd``, in which case integers encode year, month, and day
            into decimal digits,
            or ``auto``, in which case 8 digit decimals are interpretd as
            yyyymmdd and others as mjd.

        Returns
        -------
        day_obs_converter: `DayObsConverter`
            A new instance of the converter.
        """

        # If the argument is convertable to an int, do.
        if isinstance(arg, str) and int_format in ("yyyymmdd", "auto"):
            try:
                arg = datetime.datetime.strptime(arg, "%Y%m%d").date()
            except ValueError:
                pass

        match arg:
            case DayObs():
                return copy.deepcopy(arg)
            case datetime.date():
                date = arg
            case int():
                if int_format == "yyyymmdd" or (
                    len(str(arg)) == len(str("YYYYMMDD")) and int_format == "auto"
                ):
                    # Digits encode YYYYMMDD
                    date = datetime.datetime.strptime(str(arg), "%Y%m%d").date()
                else:
                    if int_format not in ("auto", "mjd"):
                        raise ValueError("Invalid integer format.")

                    date = MJD_EPOCH + datetime.timedelta(days=arg)
            case "yesterday":
                date = (datetime.datetime.now(tz=DAYOBS_TZ) - ONE_DAY).date()
            case "today" | "tonight":
                date = datetime.datetime.now(tz=DAYOBS_TZ).date()
            case "tomorrow":
                date = (datetime.datetime.now(tz=DAYOBS_TZ) + ONE_DAY).date()
            case str():
                dayobs_datetime = dateutil.parser.parse(arg)
                if dayobs_datetime.hour != 0 or dayobs_datetime.minute != 0 or dayobs_datetime.second != 0:
                    raise ValueError("The argument to from_dayobs must be a date, not a date and time.")
                if dayobs_datetime.tzinfo is not None and dayobs_datetime.tzinfo != DAYOBS_TZ:
                    raise ValueError("The argument to from_dayobs must naive or in the dayobs timezone")
                date = datetime.date(dayobs_datetime.year, dayobs_datetime.month, dayobs_datetime.day)
            case _:
                raise NotImplementedError()

        return cls(date, int_format)

    @classmethod
    def from_time(
        cls, arg: datetime.datetime | str | float | Time, int_format: IntDateFormat = "mjd"
    ) -> Self:
        """Create a representation of the dayobs that includes a given time.

        Parameters
        ----------
        arg : datetime.datetime | str | float | Time
            A time in the date to return the day_obs of.
            Floats are interpreted as Modified Julian Dates (in UTC).
            "now" is the time now.
            Representations without timezones are assumed to be in UTC.
        int_format : `str`
            If `mjd`, represent the date as an MJD when cast to an integer.
            If `yyyymmdd`, encode year month and day into decimal digits
            instead.
            `mjd` by default.

        Returns
        -------
        Returns
        -------
        day_obs_converter: `DayObsConverter`
            A new instance of the converter.
        """

        match arg:
            case datetime.datetime():
                dayobs_datetime: datetime.datetime = arg
            case "now":
                dayobs_datetime: datetime.datetime = datetime.datetime.now(tz=datetime.timezone.utc)
            case str():
                dayobs_datetime: datetime.datetime = dateutil.parser.parse(arg)
            case float():
                # Interpret floats as UTC MJDs
                maybe_datetime = Time(arg, format="mjd").datetime
                if isinstance(maybe_datetime, datetime.datetime):
                    dayobs_datetime: datetime.datetime = maybe_datetime
                else:
                    raise ValueError(f"{cls.__name__} currently only accepts scalars.")
            case Time():
                maybe_datetime = arg.datetime
                if isinstance(maybe_datetime, datetime.datetime):
                    dayobs_datetime: datetime.datetime = maybe_datetime
                else:
                    raise ValueError(f"{cls.__name__} currently only accepts scalars.")
            case _:
                raise NotImplementedError()

        assert isinstance(dayobs_datetime, datetime.datetime)

        # If dayobs_datetime is not timezone aware, assume UTC
        if dayobs_datetime.tzinfo is None:
            dayobs_datetime = dayobs_datetime.replace(tzinfo=datetime.timezone.utc)

        dayobs_date = dayobs_datetime.astimezone(DAYOBS_TZ).date()
        return cls(dayobs_date, int_format)

    @cached_property
    def yyyymmdd(self) -> int:
        return self.date.day + 100 * (self.date.month + 100 * self.date.year)

    @cached_property
    def mjd(self) -> int:
        return (self.date - MJD_EPOCH).days

    @cached_property
    def start(self) -> Time:
        start_datetime = datetime.datetime(self.date.year, self.date.month, self.date.day, tzinfo=DAYOBS_TZ)
        return Time(start_datetime)

    @cached_property
    def end(self) -> Time:
        end_datetime = (
            datetime.datetime(self.date.year, self.date.month, self.date.day, tzinfo=DAYOBS_TZ) + ONE_DAY
        )
        return Time(end_datetime)

    def __int__(self) -> int:
        return self.mjd if self.int_format in ("auto", "mjd") else self.yyyymmdd

    def __str__(self):
        return self.date.isoformat()
