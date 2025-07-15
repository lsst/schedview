import logging
import os

BAND_COLUMN_NAME_CANDIDATES = ("band", "filter")


def band_column(visits):
    """Guess the name of the column with band inforamition.

    Parameters
    ----------
    visits : `pandas.DataFrame`
       The visit data to check for a band column.

    Returns
    -------
    column_name : `str`
        The name of the column that contains the band information.
    """
    for band in BAND_COLUMN_NAME_CANDIDATES:
        if band in visits.columns:
            return band

    return BAND_COLUMN_NAME_CANDIDATES[0]


def config_logging_for_reports(stream_level: int = logging.ERROR):
    """Configure logging for a jupyter notebook that generates a report

    Parameters
    ----------
    stream_level : `int`
        Log level to actually be shown in the report.

    Notes
    -----
    If the ``SCHEDVIEW_REPORT_LOG`` environment variable is set, send
    log messages in to the file named by that variable.
    """

    # Get rid of any existing handlers of the root logger
    # so we get only those we add here.
    logging.getLogger().handlers.clear()

    # Set the format.
    log_formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
    )

    log_filename = os.environ.get("SCHEDVIEW_REPORT_LOG", "")
    if log_filename:
        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(log_formatter)
        logging.getLogger().addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_formatter)
    stream_handler.setLevel(stream_level)
    logging.getLogger().addHandler(stream_handler)

    # Send all warnings to the logger to be handled by our handlers.
    logging.captureWarnings(True)
    # If we want to configure captured warning log messages,
    # separately from other log messages,
    # get the relevant logger with logging.getLogger('py.warnings').
    # By default, it's just propogated to the root logger,
    # so is handled by the handler set above.
