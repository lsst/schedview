import datetime
import unittest
from collections import namedtuple

import astropy.units as u
import numpy as np
import pandas as pd
from astropy.coordinates import AltAz, get_body
from astropy.time import Time

from schedview import DayObs

try:
    from rubin_scheduler.site_models.almanac import Almanac

    ALMANAC = Almanac()
except ModuleNotFoundError:
    ALMANAC = None


DayObsTestData = namedtuple("DayObsTestData", ("date", "yyyymmdd", "iso_date", "mjd", "iso_times"))


class TestDayObs(unittest.TestCase):
    test_values = (
        DayObsTestData(
            datetime.date(2024, 9, 3),
            20240903,
            "2024-09-03",
            60556,
            ("2024-09-03T12:00:00Z", "2024-09-04T05:00:00Z"),
        ),
        DayObsTestData(
            datetime.date(2024, 10, 31),
            20241031,
            "2024-10-31",
            60614,
            ("2024-10-31T12:00:00Z", "2024-11-01T05:00:00Z"),
        ),
    )

    @staticmethod
    def assert_equal(dayobs, test_data):
        assert dayobs.date == test_data.date
        assert dayobs.yyyymmdd == test_data.yyyymmdd
        assert dayobs.date.isoformat() == test_data.iso_date
        assert dayobs.mjd == test_data.mjd
        assert str(dayobs) == test_data.iso_date
        if dayobs.int_format in ("mjd", "auto"):
            assert int(dayobs) == test_data.mjd
        else:
            assert int(dayobs) == test_data.yyyymmdd

    def test_dayobs(self):
        for d in self.test_values:
            self.assert_equal(DayObs.from_date(d.date), d)
            self.assert_equal(DayObs.from_date(d.yyyymmdd), d)
            self.assert_equal(DayObs.from_date(d.iso_date), d)
            self.assert_equal(DayObs.from_date(d.mjd), d)

            for iso_time in d.iso_times:
                self.assert_equal(DayObs.from_time(iso_time), d)

                t = Time(iso_time)
                self.assert_equal(DayObs.from_time(t), d)
                self.assert_equal(DayObs.from_time(t.datetime), d)
                self.assert_equal(DayObs.from_time(t.iso), d)
                self.assert_equal(DayObs.from_time(t.mjd), d)

    def test_rs_time(self):
        num_nights_tested = 1

        rng = np.random.default_rng(seed=6563)
        test_mjds = rng.choice(
            np.arange(DayObs.from_date("2024-10-01").mjd, DayObs.from_date("2036-10-01").mjd),
            num_nights_tested,
            replace=False,
        )
        test_directions = ["rise", "set"]
        test_alts = [-18, -12, -6, 0]
        test_bodies = ["sun", "moon"]

        for mjd in test_mjds:
            day_obs = DayObs.from_date(mjd, int_format="mjd")
            for body in test_bodies:
                for direction in test_directions:
                    for alt in test_alts:
                        try:
                            event_time = day_obs.body_time(body, alt, direction)
                        except ValueError:
                            # Maybe the event just never happens on night.
                            # But, the sun has the tested events every night.
                            assert body != "sun"
                            continue

                        event_altaz = AltAz(obstime=event_time, location=day_obs.location)
                        event_alt = get_body(body, event_time).transform_to(event_altaz).alt.deg
                        assert np.isclose(alt, event_alt, atol=0.01)

                        assert DayObs.from_time(event_time).mjd == day_obs.mjd

                        after_event_time = event_time + 1 * u.minute
                        after_event_altaz = AltAz(obstime=after_event_time, location=day_obs.location)
                        after_event_alt = (
                            get_body(body, after_event_time).transform_to(after_event_altaz).alt.deg
                        )

                        before_event_time = event_time - 1 * u.minute
                        before_event_altaz = AltAz(obstime=before_event_time, location=day_obs.location)
                        before_event_alt = (
                            get_body(body, before_event_time).transform_to(before_event_altaz).alt.deg
                        )

                        if direction == "rise":
                            assert before_event_alt <= alt <= after_event_alt
                        else:
                            assert before_event_alt >= alt >= after_event_alt

    @unittest.skipUnless(ALMANAC is not None, "rubin_scheduler almanac not available.")
    def test_against_almanac(self):
        num_nights_tested = 2
        almanac_times = (
            pd.DataFrame(ALMANAC.sunsets)
            .sample(num_nights_tested, random_state=42)
            .set_index("sunset", drop=False)
        )
        for sunset_mjd, night_times in almanac_times.iterrows():
            day_obs = DayObs.from_time(sunset_mjd)
            assert np.isclose(night_times.sunset, day_obs.sunset.mjd)
            assert np.isclose(night_times.sunrise, day_obs.sunrise.mjd)
            assert np.isclose(night_times.sun_n12_setting, day_obs.sun_n12_setting.mjd)
            assert np.isclose(night_times.sun_n12_rising, day_obs.sun_n12_rising.mjd)
            assert np.isclose(night_times.sun_n18_setting, day_obs.sun_n18_setting.mjd)
            assert np.isclose(night_times.sun_n18_rising, day_obs.sun_n18_rising.mjd)
            try:
                assert (
                    np.isclose(night_times.moonset, day_obs.moonset.mjd)
                    or DayObs.from_time(night_times.moonset).mjd != day_obs.mjd
                )
            except ValueError:
                # There might not be a moonset on this day_obs
                assert DayObs.from_time(night_times.moonset).mjd != day_obs.mjd

            try:
                assert (
                    np.isclose(night_times.moonrise, day_obs.moonrise.mjd)
                    or DayObs.from_time(night_times.moonrise).mjd != day_obs.mjd
                )
            except ValueError:
                # There might not be a moonrise on this day_obs
                assert DayObs.from_time(night_times.moonrise).mjd != day_obs.mjd
