# Subclasses of param.Parameter for use in schedview.

import glob

import pandas as pd
import param


class Series(param.Parameter):
    """A pandas.Series parameter."""

    def __init__(self, default=None, allow_None=False, **kwargs):
        super().__init__(default=default, allow_None=allow_None, **kwargs)
        self.allow_None = default is None or allow_None
        self._validate(default)

    def _validate_value(self, val, allow_None):
        if allow_None and val is None:
            return

        if not isinstance(val, pd.Series):
            raise ValueError(
                f"Parameter {self.name} only takes a pandas.Series, " f"not value of type {type(val)}."
            )

    def _validate(self, val):
        self._validate_value(val, self.allow_None)


class DataFrame(param.Parameter):
    """A pandas.DataFrame parameter.

    Parameters
    ----------
    `columns`: `list` [`str`] or `dict` ['str', 'type']
        The columns of the DataFrame. If a dictionary, the keys are the column
        names and the values. If a list, it contains the column names.
        If None, any set of columns is accepted.
    `allow_empty`: `bool`
        Whether to allow a DataFrame with no rows.
    """

    __slots__ = ["columns", "allow_empty"]

    def __init__(self, default=None, columns=None, allow_empty=True, allow_None=False, **kwargs):
        super().__init__(default=default, allow_None=allow_None, **kwargs)
        self.columns = columns
        self.allow_empty = allow_empty
        self.allow_None = default is None or allow_None
        self._validate(default)

    def _validate_value(self, val, allow_None):
        if allow_None and val is None:
            return
        if not isinstance(val, pd.DataFrame):
            raise ValueError(
                f"DataFarme parameter {self.name} only takes a pandas.DataFrame, "
                f"not value of type {type(val)}."
            )

        if not self.allow_empty and len(val) == 0:
            raise ValueError(f"DataFrame parameter {self.name} must have at least one row.")

        # If the DataFrame is empty, do not check columns or column types.
        if self.columns is None or len(val) == 0:
            return

        for column in self.columns:
            if column not in val.columns:
                raise ValueError(f"DataFrame parameter {self.name} must have column {column}.")

            try:
                required_type = self.columns[column]
                if not isinstance(val[column].iloc[0], required_type):
                    raise ValueError(
                        f"Column {column} of {self.name} must have type {required_type},"
                        f" but has type {type(val[column].iloc[0])}"
                    )
            except TypeError:
                pass

    def _validate(self, val):
        self._validate_value(val, self.allow_None)


class FileSelectorWithEmptyOption(param.FileSelector):
    """
    Like param.FileSelector, but allows None to be deliberately selected.
    """

    def update(self):
        self.objects = [""] + sorted(glob.glob(self.path))
        if self.default in self.objects:
            return
        self.default = self.objects[0] if self.objects else None
