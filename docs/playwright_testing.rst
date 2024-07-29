Playwright Testing
==================

Install playwright + browsers in environment
--------------------------------------------
`Install info <https://playwright.dev/python/docs/intro>`_

::

 conda activate schedview
 pip install playwright
 playwright install  # install browsers

Depending on your OS, you may also need to run:

::

 playwright install-deps

Run (headless) tests
--------------------
Tests should be run from the root (where the tests are run during workflow).
The playwright tests are disabled by default, so, to run them, the environment variable ENABLE_PLAYWRIGHT_TESTS must be set.

::

 ENABLE_PLAYWRIGHT_TESTS=1 pytest tests/test_scheduler_dashboard.py

Headed tests
------------
Tests will run in headless mode by default. If you would like to see the tests in action (headed), the tests must be run locally (where the LFA mode test will fail) or using NoMachine (or a supported equivalent).

`Instruction to set up NoMachine <https://s3df.slac.stanford.edu/public/doc/#/reference>`_

In the code, also comment/uncommment the following lines in each of the 3 classes' SetUpClass functions to swap to headed mode:

::

 cls.browser = cls.playwright.chromium.launch(headless=True)  # comment this out and uncomment the other lines
 # cls.browser = cls.playwright.chromium.launch(
 #     headless=False,
 #     slow_mo=100
 # )

Increase the 'slow_mo' parameter to slow the tests down (e.g. 500).

Debug tests
-----------
Visualise stepping through actions and assertions. Again, this needs to be run locally or using NoMachine.

`Docs <https://playwright.dev/python/docs/debug>`_

::

 ENABLE_PLAYWRIGHT_TESTS=1 PWDEBUG=1 pytest -s tests/test_scheduler_dashboard.py

Note that when actions are taken that initiate the loading indicator + pop-up messages (e.g. load pickle, change date, reset dashboard), the assertions need to be stepped through very quickly or else the events will be missed and the test will fail. Be prepared for button mashing.

Test Generator
--------------
Generates testing code as you perform actions. Again, this needs to be run locally or using NoMachine.

`Docs <https://playwright.dev/python/docs/codegen>`_

Launch server from one terminal:

::

 python schedview/app/scheduler_dashboard/scheduler_dashboard.py

Run test generator from another terminal:

::

 playwright codegen http://localhost:8080/schedview-snapshot/dashboard

