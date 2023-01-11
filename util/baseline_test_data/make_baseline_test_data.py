import gzip
import argparse
import logging
import pickle
from draft2_updated_uzy import main

SAVED_FILE_NAME = "baseline.pickle.gz"


def make_baseline_test_data():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", dest="verbose", action="store_true")
    parser.set_defaults(verbose=False)
    parser.add_argument("--survey_length", type=float, default=4)
    parser.add_argument("--outDir", type=str, default="")
    parser.add_argument(
        "--maxDither", type=float, default=0.7, help="Dither size for DDFs (deg)"
    )
    parser.add_argument(
        "--moon_illum_limit",
        type=float,
        default=40.0,
        help="illumination limit to remove u-band",
    )
    parser.add_argument("--nexp", type=int, default=2)
    parser.add_argument("--rolling_nslice", type=int, default=2)
    parser.add_argument("--rolling_strength", type=float, default=0.9)
    parser.add_argument("--dbroot", type=str)
    parser.add_argument("--gsw", type=float, default=3.0, help="good seeing weight")
    parser.add_argument("--ddf_season_frac", type=float, default=0.2)
    parser.add_argument(
        "--agg_level",
        type=str,
        default="1.5",
        help="Version of aggregation level map - either 1.5 or 2.0",
    )
    parser.add_argument("--nights_off", type=int, default=6)
    parser.add_argument("--nights_delayed", type=int, default=-1)
    parser.add_argument("--neo_night_pattern", type=int, default=4)
    parser.add_argument("--neo_filters", type=str, default="riz")
    parser.add_argument("--neo_repeat", type=int, default=4)

    args = parser.parse_args()

    observatory, scheduler, observations = main(args)
    conditions = observatory.return_conditions()
    saved_file_contents = [scheduler, conditions]

    with gzip.open(SAVED_FILE_NAME, "wb") as pickle_file:
        pickle.dump(saved_file_contents, pickle_file)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    make_baseline_test_data()
