import copy
import datetime
from dataclasses import dataclass
from functools import cached_property, partial
from typing import Literal, Self

import astropy.units as u
import dateutil.parser
import numpy as np
import scipy.optimize
from astropy.coordinates import AltAz, EarthLocation, HADec, SkyCoord, get_body
from astropy.time import Time

DAYOBS_TZ = datetime.timezone(datetime.timedelta(hours=-12))
MJD_EPOCH = datetime.date(1858, 11, 17)
ONE_DAY = datetime.timedelta(days=1)

LSE30_ATMOSPHERE = {
    "pressure": 750.0 * 100 * u.Pa,
    "temperature": 11.5 * u.deg_C,
    "relative_humidity": 0.4,
}

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
    location: EarthLocation = EarthLocation.from_geodetic(
        lon=-70.7494 * u.deg, lat=-30.2444 * u.deg, height=2650.0 * u.meter
    )
    atmosphere: dict | None = None

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
            case int() | np.int64():
                if int_format == "yyyymmdd" or (
                    len(str(arg)) == len(str("YYYYMMDD")) and int_format == "auto"
                ):
                    # Digits encode YYYYMMDD
                    date = datetime.datetime.strptime(str(arg), "%Y%m%d").date()
                else:
                    if int_format not in ("auto", "mjd"):
                        raise ValueError("Invalid integer format.")
                    # We need the cast because a np.int64 confuses the
                    # datetime.datetime constructor.
                    date = MJD_EPOCH + datetime.timedelta(days=int(arg))
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

    @cached_property
    def mean_local_solar_midnight(self):
        mjd = self.start.mjd + (-1 * self.location.lon.deg / 360 - self.start.mjd) % 1
        assert self.start.mjd <= mjd <= self.end.mjd
        return Time(mjd, format="mjd")

    @cached_property
    def mean_local_solar_noon(self):
        mjd = self.start.mjd + (self.mean_solar_midnight.mjd + 0.5 - self.start.mjd) % 1
        assert self.start.mjd <= mjd <= self.end.mjd
        return Time(mjd, format="mjd")

    def rough_body_coordinates(self, body):
        return get_body(body, time=self.mean_local_solar_midnight, location=self.location)

    def _coords_time_in_vaccuum(
        self,
        coords: SkyCoord,
        alt: float = 0.0,
        direction: Literal["rise", "set"] = "set",
    ) -> Time:
        ha_at_mean_solar_midnight = coords.transform_to(
            HADec(obstime=self.mean_local_solar_midnight, location=self.location)
        ).ha.deg
        ha_sign = -1 if direction == "rise" else 1
        cos_event_ha = (np.sin(np.radians(alt)) - np.sin(coords.dec.rad) * np.sin(self.location.lat.rad)) / (
            np.cos(coords.dec.rad) * np.cos(self.location.lat.rad)
        )
        if abs(cos_event_ha) > 1:
            raise ValueError(f"Coordinates never reach {alt} on {self}.")
        event_hour_angle = ha_sign * np.degrees(np.arccos(cos_event_ha))
        ha_diff = (event_hour_angle - ha_at_mean_solar_midnight + 180) % 360 - 180
        mjd = self.mean_local_solar_midnight.mjd + ha_diff * (0.9972696 / 360)
        mjd = self.start.mjd + (mjd - self.start.mjd) % 1
        time = Time(mjd, format="mjd")
        return time

    def body_time(
        self,
        body: Literal["sun", "moon"] = "sun",
        alt: float = 0.0,
        direction: Literal["rise", "set"] = "set",
    ) -> Time:

        if self.atmosphere is None:
            get_altaz = partial(AltAz, location=self.location)
        else:
            get_altaz = partial(AltAz, location=self.location, **self.atmosphere)

        # Get the coordinates of the body at midnight, and use direct
        # spherical trig to find when that reaches the desired alt in vaccuum.
        # This will then be used as the initial guess by the solver.
        rough_coords = self.rough_body_coordinates(body)
        rough_time = self._coords_time_in_vaccuum(rough_coords, alt, direction)

        # We'll use this to get the optimizer to go to the right minimum
        opposite_direction = "set" if direction == "rise" else "rise"
        opposite_time = self._coords_time_in_vaccuum(rough_coords, alt, opposite_direction)

        def abs_delta_alt(mjd):
            obstime = Time(mjd, format="mjd")
            sun = get_body(body, obstime)
            altaz = get_altaz(obstime=obstime)
            alt_at_mjd = sun.transform_to(altaz).alt.deg
            return np.abs(alt_at_mjd - alt)

        # Set the bounds so that the optimized minimum found is the one
        # that is closest to the rough minimum, thereby preventing it
        # from jumping to the wrong minumum (providing the setting time
        # when the rising time was requested, or vice versa).
        midpoint_mjd = (rough_time.mjd + opposite_time.mjd) / 2
        if opposite_time < rough_time:
            opt_bounds = [(max(self.start.mjd, midpoint_mjd), self.end.mjd)]
        else:
            opt_bounds = [(self.start.mjd, min(midpoint_mjd, self.end.mjd))]

        solution = scipy.optimize.minimize(abs_delta_alt, rough_time.mjd, bounds=opt_bounds, method="Powell")
        assert solution.success, f"Minimizer failed: {solution.message}"
        optimized_mjd = solution.x[0]

        # When an event does not happen at all in a day_obs (which can happen
        # for the moon, or for the sun in the arctic circle), the optimizer
        # finds a value near the bounds, and the alt at the optimized time is
        # not what we requested. Raise an exception when this happens.
        if abs_delta_alt(optimized_mjd) > 0.01:
            assert (optimized_mjd - opt_bounds[0][0] < 0.01) or (opt_bounds[0][1] - optimized_mjd < 0.01)
            raise ValueError(f"The body {body} never reaches {alt} during {direction}")

        optimized_time = Time(optimized_mjd, format="mjd")

        return optimized_time

    @cached_property
    def sunset(self):
        return self.body_time("sun", alt=0.0, direction="set")

    @cached_property
    def sunrise(self):
        return self.body_time("sun", alt=0.0, direction="rise")

    def __int__(self) -> int:
        return self.mjd if self.int_format in ("auto", "mjd") else self.yyyymmdd

    def __str__(self):
        return self.date.isoformat()