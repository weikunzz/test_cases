"""
CI sub-command for build documentation
"""
import logging
import argparse
import os
import pkgutil
import sys

from libvirt_ci import commands
from libvirt_ci import importer
from libvirt_ci import utils

LOGGER = logging.getLogger(__name__)

REQUIREMENTS = [
    "sphinx_rtd_theme",
    "sphinx-argparse",
    "sphinxcontrib-programoutput",
    "sphinxcontrib-confluencebuilder",
]


def import_mod():
    """
    Use importer to import all commands before generating docs.
    This will install all requirements or sphinx autodoc will fail when
    importing dependent packages
    """
    cmd_mod = {}
    cmd_path = commands.__path__
    for _, mod_name, is_pkg in pkgutil.iter_modules(cmd_path):
        if is_pkg:
            continue
        mod = importer.import_module('libvirt_ci.commands.' + mod_name)
        cmd_mod[mod_name.replace('_', '-')] = mod

    return cmd_mod


def parse_args():
    """
    Parse commands modules arguments and return parser
    """
    cmd_mod = import_mod()
    parser = argparse.ArgumentParser(
        description='Command line tool for libvirt CI project')

    subparsers = parser.add_subparsers(dest='command')

    for sub_command, mod in cmd_mod.iteritems():
        sys.argv = ['', ]
        sys.argv.append(sub_command)
        subparser = subparsers.add_parser(sub_command, help=mod.__doc__)
        mod.parse(subparser)

    parser.parse_args()

    return parser


# pylint: disable=unused-argument
def run(params):
    """
    Main function to building documentation.
    """
    import_mod()
    os.chdir("docs")

    result = utils.run("make html")
    if result.exit_status != 'success':
        LOGGER.error(result)


def parse(parser):
    """
    Parse arguments for building documentation.
    """
