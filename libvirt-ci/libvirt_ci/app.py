"""
The libvirt-ci main application
"""
import os
import sys
import argparse
import logging
import pkgutil

from libvirt_ci import commands
from libvirt_ci import importer
from libvirt_ci.params import Parameters

from libvirt_ci.config import setup_config
from libvirt_ci.data import setup_data_dir
from libvirt_ci.logger import setup_root_logger

PROG = 'ci'
DESCRIPTION = 'Command line tool for libvirt CI project'

LOGGER = logging.getLogger(__name__)


class CIApp(object):
    """
    libvirt-ci application
    """

    def __init__(self):
        self.sub_command = None
        self.submod = None
        self._run = None
        self.setup()
        self.subcommands()
        self.args = argparse.Namespace()
        self.application = argparse.ArgumentParser(
            prog=PROG,
            add_help=False,
            description=DESCRIPTION,
            usage=self.usage())

    def setup(self):
        setup_config()
        setup_data_dir()
        setup_root_logger()

    def usage(self):
        """
        Custom usage message
        """
        cmds = ' | '.join(self.sub_commands)
        return '%s [%s]' % (PROG, cmds)

    def subcommands(self):
        """
        Get all the supported sucommands' name
        """
        self.sub_commands = [
            name.replace('_', '-') for _, name, ispkg in pkgutil.iter_modules(
                commands.__path__) if not ispkg]

    def _parse_args(self):
        """
        Start to parsing sub command arguments
        """
        self.application = argparse.ArgumentParser(prog=PROG,
                                                   description=DESCRIPTION,
                                                   parents=[self.application])
        if self.sub_command and self.submod:
            subparsers = self.application.add_subparsers(
                title='subcommands',
                description='valid subcommands',
                help='subcommand help',
                dest='command')
            subparser = subparsers.add_parser(
                self.sub_command,
                help=self.submod.__doc__)
            self.submod.parse(subparser)
        else:
            return

        self.args, extra_args = self.application.parse_known_args()

        extra_params = {}
        opt = None
        for arg in extra_args:
            if arg.startswith('--'):
                opt = arg[2:].replace('-', '_')
                extra_params[opt] = []
            else:
                if opt is None:
                    raise ValueError('Unexpected argument %s' % arg)
                else:
                    extra_params[opt].append(arg)

        for key, val_list in extra_params.iteritems():
            if len(val_list) == 1:
                setattr(self.args, key, val_list[0])
            elif len(val_list) == 0:
                setattr(self.args, key, True)
            else:
                setattr(self.args, key, val_list)
        return self.args

    def _get_params(self):
        """
        Setup parameters from all possible resources
        """
        params = Parameters()

        # Get parameters from command line arguments
        args = self._parse_args()
        if args is None:
            return
        for key, value in vars(args).items():
            setattr(params, key, value)

        params_dict = {}
        # Get parameters from environment variables
        for key, value in os.environ.items():
            if key.startswith('CI_'):
                params_dict[key[3:].lower()] = value

        for key, value in params_dict.items():
            if value and hasattr(params, key):
                old_value = getattr(params, key)
                if isinstance(old_value, bool):
                    if str(value).lower() == 'true':
                        new_value = True
                    else:
                        new_value = False
                else:
                    new_value = value

                if new_value != old_value:
                    LOGGER.debug(
                        "Replacing parameter '%s' with env ('%s'->'%s')",
                        key, old_value, new_value)
                    setattr(params, key, new_value)

        LOGGER.debug("Test parameters:\n%s", params)
        return params

    def import_subcommand(self):
        """
        Import module of the sub command
        """
        try:
            self.sub_command = sys.argv[1]
            if self.sub_command not in self.sub_commands:
                raise IndexError
            mod_name = self.sub_command.replace('-', '_')
            self.submod = importer.import_module('libvirt_ci.commands.' + mod_name)
            self._run = self.submod.run
        except IndexError:
            self.application.print_help()
            sys.exit(1)

    def run(self):
        """
        Main entrance function
        """
        self.import_subcommand()
        params = self._get_params()
        if params is None:
            self.application.print_help()
            sys.exit(1)
        self._run(params)
