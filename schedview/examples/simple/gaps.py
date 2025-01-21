import argparse

import astropy.utils.iers
import lsst.resources
import pandas as pd
import rubin_sim.maf

import schedview.collect
import schedview.compute
import schedview.compute.visits
import schedview.dayobs
import schedview.plot

astropy.utils.iers.conf.iers_degraded_accuracy = "ignore"


def make_overhead_summary_table(iso_date: str, sim_resource_path: str, output_file: str):
    # Parameters
    sim_resouce_path = lsst.resources.ResourcePath(sim_resource_path)
    day_obs = schedview.dayobs.DayObs.from_date(iso_date)

    # Collect
    visits: pd.DataFrame = schedview.collect.read_opsim(
        sim_resouce_path,
        constraint=f"FLOOR(observationStartMJD-0.5)={day_obs.mjd}",
        stackers=[rubin_sim.maf.stackers.OverheadStacker()],
    )

    # Compute
    night_events: pd.DataFrame = schedview.compute.astro.night_events(day_obs.date)
    overhead_summary: dict = schedview.compute.visits.compute_overhead_summary(
        visits, night_events.loc["sun_n12_setting", "MJD"], night_events.loc["sun_n12_rising", "MJD"]
    )
    """A dictionary summarizing the overheads of the visits."""

    # Plot
    summary_table: str = schedview.plot.create_overhead_summary_table(overhead_summary)
    """An HTML definition list summarizing the overheads of the visits."""

    # Report
    with open(output_file, "w") as report_io:
        print(f"<html><body>{summary_table}</body></html>", file=report_io)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute and report overhead summary for a given date.")
    parser.add_argument(
        "date", type=str, help="The date for which to compute the overhead summary (YYYY-MM-DD)."
    )
    parser.add_argument("sim_resource_path", type=str, help="The simulation resource path.")
    parser.add_argument("output_file", type=str, help="The output file to save the report.")
    args = parser.parse_args()
    make_overhead_summary_table(args.date, args.sim_resource_path, args.output_file)
