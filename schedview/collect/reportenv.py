import platform

import pandas as pd
import rubin_scheduler
import rubin_sim

from .. import __version__ as schedview_version


def get_report_sw_versions():
    report_sw_versions = pd.DataFrame(
        columns=["package_version"],
        index=pd.Index([], name="package_name"),
    )
    report_sw_versions.loc["python", "package_version"] = platform.python_version()
    report_sw_versions.loc["rubin-scheduler", "package_version"] = rubin_scheduler.__version__
    report_sw_versions.loc["rubin-sim", "package_version"] = rubin_sim.__version__
    report_sw_versions.loc["schedview", "package_version"] = schedview_version
    return report_sw_versions
