"""
Self check module
"""
import logging
import pkgutil
import coverage
import pytest
import pycodestyle
from pylint import epylint
import yaml

import libvirt_ci
from libvirt_ci import importer
from libvirt_ci import utils

from libvirt_ci.config import CONFIG_PATH

import test

LOGGER = logging.getLogger(__name__)

REQUIREMENTS = [
    "jenkins-job-builder",
]


def check_code_style():
    LOGGER.info("=" * 80)
    LOGGER.info("Checking code style / PEP8 checking")
    LOGGER.info("-" * 80)
    style = pycodestyle.StyleGuide(
        paths=['libvirt_ci', 'bin/ci'],
        ignore=['E501'])
    result = style.check_files()
    if result.total_errors:
        raise Exception("Failed when checking code style")
    LOGGER.info("Passed")


def static_analysis():
    LOGGER.info("=" * 80)
    LOGGER.info("Running static analysis / pylint checking")
    LOGGER.info("-" * 80)
    stdout, _ = epylint.py_run(
        'libvirt_ci bin/ci --disable=R,C,locally-disabled,fixme '
        '--unsafe-load-any-extension=y',
        return_std=True)
    result = stdout.getvalue().strip()
    if "warn" in result or "error" in result:
        print result
        raise Exception("Failed when running static analysis")
    LOGGER.info("Passed")


def validate_blacklist():
    """
    Validate a blacklist YAML file.
    Raise an exception if any error found.
    """
    TYPE_KEYS_MAP = {
        'not-supported': ['feature'],
        'bug-wont-fix': ['bug'],
        'bug-not-fixed': ['bug'],
        'case-updating': ['task'],
        'hazardous-case': ['reason'],
        'need-env': ['env'],
        'not-in-plan': ['reason'],
    }

    blacklist_path = '%s/blacklist.yaml' % CONFIG_PATH

    LOGGER.info("=" * 80)
    LOGGER.info("Validating blacklist in %s", blacklist_path)
    LOGGER.info("-" * 80)

    with open(blacklist_path) as blacklist_fp:
        blacklist = yaml.load(blacklist_fp)

    conditions = set()
    for scenario in blacklist:
        if 'description' not in scenario:
            raise Exception("'description' must exists in %s" % scenario)
        if 'when' in scenario:
            condition = scenario['when']
        else:
            condition = None

        if condition in conditions:
            raise Exception("Duplicated 'when' found: %s" % condition)
        conditions.add(condition)

        for blacklist_type, blacklists in scenario.items():
            if blacklist_type in ['when', 'description']:
                continue

            if blacklist_type in TYPE_KEYS_MAP:
                required_keys = TYPE_KEYS_MAP[blacklist_type] + ['test']
                for blacklist in blacklists:
                    for key in required_keys:
                        if key not in blacklist:
                            raise Exception("Key '%s' should exists in %s" %
                                            (key, blacklist))
            else:
                raise Exception('Unknown type %s, should be one of %s' %
                                (blacklist_type, TYPE_KEYS_MAP.keys()))
    LOGGER.info("Validated")


def check_jobs():
    LOGGER.info("=" * 80)
    LOGGER.info("Checking Jenkins jobs")
    LOGGER.info("-" * 80)

    result = utils.run("python ./bin/ci update-jobs --test")
    if result.exit_status != 'success':
        raise Exception("Failed when checking jobs:\n%s" % result)
    LOGGER.info("Passed")


def run_unittests():
    LOGGER.info("=" * 80)
    LOGGER.info("Running unit tests")
    LOGGER.info("-" * 80)

    cov = coverage.Coverage(
        branch=True,
        omit=["*/lib/python*"],
    )
    cov.start()

    ret = pytest.main(['-x', 'test'])

    cov.stop()
    cov.save()
    cov.xml_report()
    cov.html_report()
    if ret != 0:
        raise Exception("Failed when run unit test:\n%s" % ret)

    LOGGER.info("Passed")


# pylint: disable=unused-argument
def run(params):
    """
    Main function to check libvirt-ci itself.
    """

    libvirt_ci_path = libvirt_ci.__path__
    for _, mod_name, is_pkg in pkgutil.iter_modules(libvirt_ci_path):
        if is_pkg:
            continue
        importer.import_module('libvirt_ci.' + mod_name)

    commands_path = importer.import_module('libvirt_ci.commands').__path__
    for _, mod_name, is_pkg in pkgutil.iter_modules(commands_path):
        if is_pkg:
            continue
        importer.import_module('libvirt_ci.commands.' + mod_name)

    runner_path = importer.import_module('libvirt_ci.runner').__path__
    for _, mod_name, is_pkg in pkgutil.iter_modules(runner_path):
        if is_pkg:
            continue
        importer.import_module('libvirt_ci.runner.' + mod_name)

    provision_path = importer.import_module('libvirt_ci.provision').__path__
    for _, mod_name, is_pkg in pkgutil.iter_modules(provision_path):
        if is_pkg:
            continue
        importer.import_module('libvirt_ci.provision.' + mod_name)

    env_path = importer.import_module('libvirt_ci.env').__path__
    for _, mod_name, is_pkg in pkgutil.iter_modules(env_path):
        if is_pkg:
            continue
        importer.import_module('libvirt_ci.env.' + mod_name)

    test_path = test.__path__
    for _, mod_name, is_pkg in pkgutil.iter_modules(test_path):
        if is_pkg:
            continue
        importer.import_module('test.' + mod_name)

    check_code_style()
    static_analysis()
    validate_blacklist()
    check_jobs()
    run_unittests()


def parse(parser):
    """
    Parse arguments for checking libvirt-ci itself.
    """
