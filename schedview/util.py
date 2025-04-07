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
