import panel as pn

import schedview
import schedview.param
from schedview.app.scheduler_dashboard.constants import PACKAGE_DATA_DIR
from schedview.app.scheduler_dashboard.unrestricted_scheduler_snapshot_dashboard import (
    SchedulerSnapshotDashboard,
)


class RestrictedSchedulerSnapshotDashboard(SchedulerSnapshotDashboard):
    """A Parametrized container for parameters, data, and panel objects for the
    scheduler dashboard working in restricted more where data files can only
    be loaded from a certain data directory that is set through constructor.
    """

    scheduler_fname_doc = """URL or file name of the scheduler pickle file.
    Such a pickle file can either be of an instance of a subclass of
    rubin_scheduler.scheduler.schedulers.CoreScheduler, or a tuple of the form
    (scheduler, conditions), where scheduler is an instance of a subclass of
    rubin_scheduler.scheduler.schedulers.CoreScheduler, and conditions is an
    instance of rubin_scheduler.scheduler.conditions.Conditions.
    """
    scheduler_fname = schedview.param.FileSelectorWithEmptyOption(
        path=f"{PACKAGE_DATA_DIR}/*scheduler*.p*",
        doc=scheduler_fname_doc,
        default=None,
        allow_None=True,
    )

    data_loading_widgets = {
        "widget_datetime": pn.widgets.DatetimePicker,
    }

    def __init__(self, data_dir=None):
        super().__init__()

        if data_dir is not None:
            self.param["scheduler_fname"].update(path=f"{data_dir}/*scheduler*.p*")
