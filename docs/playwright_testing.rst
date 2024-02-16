Playwright Testing
==================

Install playwright + browsers in environment
--------------------------------------------
`Install info <https://playwright.dev/python/docs/intro>`_

::

 conda activate schedview
 conda install playwright
 playwright install  # install browsers

Depending on your OS, you may also need to run:

::

 playwright install-deps

Run tests
---------

::

 cd tests
 pytest test_scheduler_dashboard.py

Test Generator
--------------
Generates testing code as you perform actions.

`Docs <https://playwright.dev/python/docs/codegen>`_

Launch server from one terminal:

::

 cd schedview/app/scheduler_dashboard
 python scheduler_dashboard.py

Run test generator from another terminal:

::

 playwright codegen http://localhost:8080/schedview-snapshot/dashboard

Debug tests
-----------
Visualise stepping through actions and assertions.

`Docs <https://playwright.dev/python/docs/debug>`_

::

 cd tests
 PWDEBUG=1 pytest -s test_scheduler_dashboard.py
