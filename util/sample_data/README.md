# Generation of sample data

The program here generates sample data for demonstrating schedview
applications.

It can be run directly:

```
python make_sample_test_data.py
```

There is a `--help` option to describe optional parameters.

The primary use for it is to generate or update sample data for use in
`${SCHEDVIEW_DIR}/schedview/data`.

Pytest now uses the same generation logic through
`tests/conftest.py`, which creates sample data in a local cache under
`.pytest_cache/` and points tests at that directory with
`SCHEDVIEW_SAMPLE_DATA_DIR` and `SCHED_PICKLE`.

The script remains useful when you want to refresh the checked-in sample
artifacts manually.

To copy the generated files into place:

```
cp sample_* ../../schedview/data
```
