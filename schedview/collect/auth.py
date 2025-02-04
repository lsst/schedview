import os
from functools import cache

try:
    import lsst.rsp

    @cache
    def get_auth(*args, **kwargs) -> tuple[str, str]:
        return ("user", lsst.rsp.get_access_token(*args, **kwargs))

except ImportError:

    @cache
    def get_auth(token_file: str | None = None) -> tuple[str, str]:
        token: str | None = None

        if token_file is not None:
            with open("token_file", "r") as f:
                token = f.read()
        elif "ACCESS_TOKEN" in os.environ:
            token = os.environ.get("ACCESS_TOKEN")

        if token is None:
            raise ValueError("No access token found.")

        return ("user", token)
