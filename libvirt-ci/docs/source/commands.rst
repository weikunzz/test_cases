The CI Command and Modules
**************************

The CI Command
==============

To see what ci command line tool support, simply run::

  $ ci --help

.. program-output:: python bin/ci --help
   :cwd: ../..

For check sub-commands, e.g. check sub-command update-jobs::

  $ ci update-jobs --help

.. program-output:: python bin/ci update-jobs --help
   :cwd: ../..

Please check :ref:`CI Command Reference` for command line reference.

Add or Update CI Command
========================

All ci command source code are under repo dir::

    libvirt_ci/commands/

Two functions are required in each commands python file:

1. The main entrance function

.. code:: python

  def run(params):
      """
      Main function to run the command
      """
      ...

2. The arguments parser function

.. code:: python

  def parse(parser):
      """
      Parse arguments for run the command
      """
      ...

The CI Modules
==============

All libvirt ci common modules could be found under repo dir::

    libvirt_ci/

the common modules are wrappers for

    * utils functions
    * interact with other services
    * test runners (:ref:`Test Runner`)

When add new command, please use or update the common libraires already exists
in the repo.

If new service wrappers needed, please add new one.

The supported utils functions modules are::

    abce.py - An enhanced version of python abc
    data_dir.py - Library to help libvirt_ci find important data paths.
    log.py - Generate a logger for a module
    metadata.py - Helper functions for get/set testing related metadata.
    package.py - Module to manage yum package related manipulations
    params.py - Class to collect all the parameters used for testing
    report.py - Generate and control the report functions
    state.py - Monitor testing env state and recover if needed
    utils.py - Library for libvirt_ci related helper functions and classes
    env/ - Manage test environment

The helpers with explicit service name include::

    coverage.py - The coverage helper with virtcov support
    gdata.py - Use Google spreadsheet as data storage
    github.py - Module to manage github related manipulations
    jenkins_job.py - Classes for job generation, include parser for support
                     specific yaml rules
    jira.py - Class of jira service operation
    mail.py - Wrapper module to manager email sending
    teiid.py - Class of teiid service operation
    yum_repos.py - Manage yum repo as objects and includes several helper
                   function to generate useful yum repos.

Please check :ref:`libvirt_ci` for all libvirt CI modules.
