import io
import urllib.parse
from contextlib import redirect_stdout

BASE_PRENIGHT_URL = urllib.parse.urlunparse(
    (
        "https",
        "usdf-rsp.slac.stanford.edu",
        "times-square/github/lsst/schedview_notebooks/prenight/prenight",
        "",
        "",
        "",
    )
)


def tabulate_sim_archive_metadata(sim_metadata, day_obs=None):
    """Create an HTML table of simulations given simulation metadata.

    Parameters
    ----------
    sim_metadata : `dict`
        A dictionary of dictionaries of simulation metadata, as produced
        by `schedview.compute.munge_sim_archive_metadata`.
    day_obs : `str`
        The date for which to provide the link in the table.

    Returns
    -------
    table_html : `str`
        An HTML table suitable for inclusion in a web page or jupyter notebook.
    """
    sim_table_html = io.StringIO()
    with redirect_stdout(sim_table_html):
        print("<table>")
        print("<thead><tr>")
        print(" <th>Date simulation addad to archive</th>")
        print(" <th>id</th>")
        print(" <th>simulation</th>")
        print(" <th>first day_obs</th>")
        print(" <th>last day_obs</th>")
        print(" <th>scheduler version</th>")
        print(" <th>tags</th>")
        print("</tr></thead>")
        print("<tbody>")
        for sim_name, metadata in sim_metadata.items():
            sim_date = metadata["sim_execution_date"]
            sim_index = metadata["sim_index"]
            link_day_obs = metadata["simulated_dates"]["first_day_obs"] if day_obs is None else day_obs
            url = f"{BASE_PRENIGHT_URL}?day_obs={link_day_obs}&sim_date={sim_date}&sim_index={sim_index}"
            abbreviated_label = metadata["label"].removeprefix(f"{sim_date}/{sim_index}")
            print("<tr>")
            print(f"<td>{sim_date}</td>")
            print(f"<td>{sim_index}</td>")
            print(
                f'<td><a href="{url}" target="_blank" rel="noopener noreferrer">{abbreviated_label}</a></td>'
            )
            print(f"<td>{metadata['simulated_dates']['first_day_obs']}</td>")
            print(f"<td>{metadata['simulated_dates']['last_day_obs']}</td>")
            print(
                f"<td>{metadata['scheduler_version'] if 'scheduler_version' in metadata else 'unknown'}</td>"
            )
            if "tags" in metadata:
                print(f"<td>{str(metadata['tags'])}</td>")
            else:
                print("<td></td>")
            print("</tr>")

        print("</tbody>")
        print("</table>")
        print()

    return sim_table_html.getvalue()
