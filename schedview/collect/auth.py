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
        token = os.environ.get("ACCESS_TOKEN")
        if token is None and token_file is not None:
            with open("token_file", "r") as f:
                token = f.read()

        if not isinstance(token, str):
            raise ValueError("No access token found.")

        return ("user", token)
