import pandas as pd
from astropy.time import Time
from lsst.ts.xml.enums.Script import ScriptState

from schedview.dayobs import DayObs


def collapse_script_logevents(script_logevents: pd.DataFrame | list) -> pd.DataFrame:
    script_logevents = pd.DataFrame(script_logevents)

    script_logevents["scriptStateName"] = script_logevents["scriptState"].map(
        {k: ScriptState(k).name for k in ScriptState}
    )

    for col in [c for c in script_logevents.columns if c.startswith("timestamp")]:
        script_logevents[col.removeprefix("timestamp")] = Time(
            script_logevents[col], format="unix_tai"
        ).datetime64

    state_times = (
        script_logevents.reset_index()
        .groupby(["scriptSalIndex", "scriptStateName"])
        .agg("last")
        .reset_index(["scriptStateName"])
        .pivot(columns=["scriptStateName"], values=["time"])
        .droplevel(0, axis="columns")
    )
    last_values = script_logevents.groupby("scriptSalIndex").agg("last")
    first_times = script_logevents.reset_index().groupby("scriptSalIndex").agg({"time": "min"})
    last_times = script_logevents.reset_index().groupby("scriptSalIndex").agg({"time": "max"})
    collapsed_script = state_times.join(last_values)
    collapsed_script.insert(0, "last_logevent_time", last_times)
    collapsed_script.insert(0, "first_logevent_time", first_times)
    return collapsed_script


def find_script_stage_spans(scripts: pd.DataFrame | list, day_obs: DayObs) -> pd.DataFrame:
    """Create a table of script events with start and end times for the
    configure and process stages.

    Parameters
    ----------
    scripts : `pd.DataFrame` or `list`
        Data as returned from a query to
        the lsst.sal.ScriptQueue.logevent_script channel of the EFD.

    Returns
    -------
    pd.DataFrame
        The DataFrame with added `stage`, `start_time`, and `end_time`
        columns.
    """
    scripts = collapse_script_logevents(scripts)

    stage_spans = []
    for stage in ("Configure", "Process"):
        these_spans = scripts.copy()
        these_spans.insert(0, "end_time", scripts[f"{stage}End"])
        these_spans.insert(0, "start_time", scripts[f"{stage}Start"])
        these_spans.insert(0, "stage", stage)

        stage_spans.append(these_spans)

    script_spans = pd.concat(stage_spans)
    script_spans = script_spans.loc[
        (script_spans["start_time"] < day_obs.end.datetime64)
        & (script_spans["start_time"] > day_obs.start.datetime64)
        & (script_spans["end_time"] < day_obs.end.datetime64)
        & (script_spans["end_time"] > day_obs.start.datetime64),
        :,
    ]

    return script_spans
