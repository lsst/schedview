import argparse

from schedview.testing.sample_data import _default_sample_date, write_sample_data

DEFAULT_DATE = _default_sample_date()


def make_sample_test_data():
    parser = argparse.ArgumentParser(description="Generate sample test data for testing schedview.")
    parser.add_argument(
        "--opsim_output_fname",
        type=str,
        default="sample_opsim.db",
        help="Filename for the opsim output.",
    )
    parser.add_argument(
        "--scheduler_fname",
        type=str,
        default="sample_scheduler.pickle.xz",
        help="Filename for the scheduler pickle file.",
    )
    parser.add_argument(
        "--rewards_fname",
        type=str,
        default="sample_rewards.h5",
        help="Filename for the rewards file.",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=DEFAULT_DATE,
        help="Date of the night to simulate (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="The number of hours to simulate (defaults to one night).",
    )
    args = parser.parse_args()

    write_sample_data(
        args.opsim_output_fname,
        args.scheduler_fname,
        args.rewards_fname,
        date=args.date,
        duration=args.duration,
    )


if __name__ == "__main__":
    make_sample_test_data()
