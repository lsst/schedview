import numpy as np
import pandas as pd


def summarize_blocks(data: list[dict]) -> pd.DataFrame:
    """ "Summarize a DataFrame of observing blocks.

    Parameters
    ----------
    data : `list`
        The list of dictionaries as returned by a query to the EFD, with
        at least these keys in the dicts (mapped from EFD fields): ``"id"``,
        ``"definition"``, ``"executionsCompleted"``, ``"hash"``, ``"salIndex"``

    Returns
    -------
    summary : `pd.DataFrame`
        The summary data frame.
    """

    if len(data) < 1:
        return pd.DataFrame()

    block_status = pd.DataFrame(data)

    sorted_block_status = block_status.sort_values("id")
    initial_block_status = sorted_block_status.groupby("id")[
        ["id", "definition", "executionsCompleted", "hash", "salIndex"]
    ].agg("first")
    final_block_status = sorted_block_status.groupby("id")[
        ["id", "definition", "executionsCompleted", "hash", "salIndex"]
    ].agg("last")

    block_summary = final_block_status.loc[:, ["id", "definition", "hash", "executionsCompleted"]]
    block_summary["night_executions"] = (
        final_block_status["executionsCompleted"] - initial_block_status["executionsCompleted"]
    )
    return block_summary


def compute_block_spans(data: list[dict]) -> pd.DataFrame:
    block_status = pd.DataFrame(data)
    block_status["first"] = (
        (block_status["status"] == "STARTED")
        | (block_status["hash"] != block_status["hash"].shift())
        | (block_status["executionsCompleted"] != block_status["executionsCompleted"].shift())
        | (block_status["status"].shift() == "COMPLETED")
        | (block_status["status"].shift() == "ERROR")
    )
    # The status before the first of a sequence is the last of the previous
    block_status["last"] = block_status["first"].shift(-1)

    # Treat of the first and last statuses we have as the first and
    # last of their respective sequences.

    first_iloc = block_status.columns.get_loc("first")
    last_iloc = block_status.columns.get_loc("last")
    # make type checkers happy by verifying that we don't have multiple
    # columns with the same name
    assert isinstance(first_iloc, int)
    assert isinstance(last_iloc, int)
    block_status.iloc[0, first_iloc] = True
    block_status.iloc[-1, last_iloc] = True

    block_status["start_time"] = block_status.index.values
    block_status["end_time"] = np.where(
        block_status["last"], block_status["start_time"], block_status["start_time"].shift(-1)
    )
    return block_status
