To make a new pickle of test data based on the baseline, begin by updating
the submodule with the simulation driver. In the `$SCHEDVIEW_DIR/utils` 
directory, run:
```
git submodule update sims_featureScheduler_runs3.0
```

Then, run `make_baseline_test_data.py` from the
`$SCHEDVIEW_DIR/utils/baseline_test_data` directory:
```
python make_baseline_test_data.py
```

This will create the test data file, by default `baseline.pickle.gz`