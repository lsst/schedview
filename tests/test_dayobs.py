import datetime
import unittest
from collections import namedtuple

from astropy.time import Time

from schedview import DayObs

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
