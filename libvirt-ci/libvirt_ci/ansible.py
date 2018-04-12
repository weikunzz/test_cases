"""
Module to manage run ansible with api and return result
"""
from __future__ import absolute_import

import logging
import json

from functools import wraps
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.plugins.callback.default import CallbackModule as DefaultCallback
from ansible.plugins.callback import CallbackBase
from ansible import constants as C

try:
    from ansible.vars import VariableManager
except ImportError:
    VariableManager = None
    from ansible.vars.manager import VariableManager as VariableManager_

try:
    from ansible.inventory.manager import InventoryManager
except ImportError:
    InventoryManager = None
    from ansible.inventory import Inventory

LOGGER = logging.getLogger(__name__)


def _prepare_play_reqs(inventory, extra_vars):
    """
    As ansible is chaning the API, use a function to wrap up
    https://github.com/ansible/ansible/commit/8f97aef1a365cbbbb822d6d09f96af17a076b295
    Basically a copy of "_play_prereqs" function
    """
    # all needs loader
    loader = DataLoader()
    if VariableManager:
        variable_manager = VariableManager()
    else:
        variable_manager = VariableManager_(loader=loader)
    variable_manager.extra_vars = extra_vars
    variable_manager.host_key_checking = False

    # create the inventory, and filter it based on the subset specified (if any)
    if InventoryManager:
        inventory = InventoryManager(loader=loader, sources=inventory)
    else:
        inventory = Inventory(loader=loader, variable_manager=variable_manager, host_list=inventory)

    variable_manager.set_inventory(inventory)

    return loader, inventory, variable_manager


# pylint: disable=protected-access
def _result_wrapper(func):
    """ This is not a method """
    @wraps(func)
    def wrapper(self, result, **kwargs):
        func(self, result, **kwargs)
        host, result = result._host, result._result
        self.results.append(result)
        LOGGER.debug(json.dumps({host.name: result}, indent=4))
    return wrapper


class WrappedDefaultCallback(DefaultCallback):
    """
    A callback plugged into default plugin, making use of ansible's
    default display, while collecting results
    """

    def __init__(self, *args, **kwargs):
        self.results = []
        super(WrappedDefaultCallback, self).__init__(*args, **kwargs)

    @property
    def last_result(self):
        return self.results[-1] if self.results else None

    v2_runner_on_ok = _result_wrapper(DefaultCallback.v2_runner_on_ok)
    v2_runner_on_failed = _result_wrapper(DefaultCallback.v2_runner_on_failed)
    v2_runner_on_unreachable = _result_wrapper(DefaultCallback.v2_runner_on_unreachable)
    v2_runner_on_skipped = _result_wrapper(DefaultCallback.v2_runner_on_skipped)


class ResultCollectCallback(CallbackBase):
    """A sample callback plugin used for performing an action as results come in

    If you want to collect all results into a single object for processing at
    the end of the execution, look into utilizing the ``json`` callback plugin
    or writing your own custom callback plugin
    """

    def __init__(self, *args, **kwargs):
        self.last_result = None
        super(ResultCollectCallback, self).__init__(*args, **kwargs)

    # pylint: disable=arguments-differ,protected-access,unused-argument
    def v2_runner_on_ok(self, result, **kwargs):
        """Print a json representation of the result
        This method could store the result in an instance attribute for
        retrieval later
        """
        host = result._host
        self.last_result = result._result
        LOGGER.debug(json.dumps({host.name: result._result}, indent=4))

    v2_runner_on_failed = v2_runner_on_ok
    v2_runner_on_unreachable = v2_runner_on_ok
    v2_runner_on_skipped = v2_runner_on_ok


class Ansible(object):
    """
    Ansible wrapper
    """
    def __init__(self, host_list='localhost', private_key=None, ssh_args=None,
                 extra_vars=None, tags=None, verbosity=None):
        # initialize needed objects
        self.passwords = {}
        options = namedtuple('Options', ['listtags', 'listtasks', 'listhosts',
                                         'syntax', 'connection', 'module_path',
                                         'forks', 'remote_user',
                                         'private_key_file', 'ssh_common_args',
                                         'ssh_extra_args', 'sftp_extra_args',
                                         'scp_extra_args', 'become',
                                         'become_method', 'become_user',
                                         'verbosity', 'check', 'tags', 'diff'])
        self.options = options(listtags=False, listtasks=False,
                               listhosts=False, syntax=False,
                               connection='ssh', module_path=None, forks=100,
                               remote_user='slotlocker',
                               private_key_file=private_key,
                               ssh_common_args=ssh_args, ssh_extra_args=None,
                               sftp_extra_args=None, scp_extra_args=None,
                               become=False, become_method='sudo',
                               become_user='root', verbosity=verbosity,
                               check=False, diff=False, tags=tags or [])
        self.loader, self.inventory, self.variable_manager = _prepare_play_reqs(
            host_list, extra_vars)

    def run_playbook(self, playbook_path):
        """
        Run playbook and return last task's result
        """
        LOGGER.debug("Run playbook: %s", playbook_path)
        task_list = self.loader.load_from_file(playbook_path)
        LOGGER.debug("task_list is %s", task_list)

        # Override ansible default callback
        if len(task_list) == 1 and len(task_list[0]['tasks']) == 1:
            # When there are strictly only one task, bypss console output to prevent span
            results_callback = ResultCollectCallback()
        else:
            results_callback = WrappedDefaultCallback()
        setattr(C, 'DEFAULT_STDOUT_CALLBACK', results_callback)
        setattr(C, 'HOST_KEY_CHECKING', False)
        setattr(C, 'RETRY_FILES_ENABLED', False)

        pbex = PlaybookExecutor(playbooks=[playbook_path],
                                inventory=self.inventory,
                                variable_manager=self.variable_manager,
                                loader=self.loader,
                                options=self.options,
                                passwords=self.passwords)
        result = pbex.run()

        last_result = results_callback.last_result
        if not results_callback.last_result:
            LOGGER.error("Didn't get any result.")

        return result, last_result
