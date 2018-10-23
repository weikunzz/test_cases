# -*- coding: utf-8 -*-

from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase


class PingCallback(CallbackBase):
    def __init__(self):
        super(PingCallback, self).__init__()
        self._result = {}

    def get_result(self):
        return self._result

    def runner_on_ok(self, host, res):
        self._result[host] = {"status": True}

    def runner_on_failed(self, host, res, ignore_errors=False):
        self.runner_on_ok(host, res)

    def runner_on_unreachable(self, host, res):
        self._result[host] = {"status": False}


class ShellCallback(CallbackBase):
    def __init__(self):
        super(ShellCallback, self).__init__()
        self._result = {}

    def get_result(self):
        return self._result

    def runner_on_ok(self, host, res):
        ret_code = -1
        std_out = ""
        std_err = ""
        if isinstance(res, dict):
            if "rc" in res:
                ret_code = res["rc"]
            if "stdout" in res:
                std_out = res["stdout"]
            if "stderr" in res:
                std_err += res["stderr"]
        self._result[host] = {"retcode": ret_code, "stdout": std_out, "stderr": std_err}

    def runner_on_failed(self, host, res, ignore_errors=False):
        self.runner_on_ok(host, res)

    def runner_on_unreachable(self, host, res):
        std_err = ""
        if isinstance(res, dict) and "msg" in res:
            std_err = res["msg"]
        self._result[host] = {"retcode": -1, "stdout": "", "stderr": std_err}


class CopyCallback(CallbackBase):
    def __init__(self):
        super(CopyCallback, self).__init__()
        self._result = {}

    def get_result(self):
        return self._result

    def runner_on_ok(self, host, res):
        self._result[host] = {"retcode": 0, "retout": ""}

    def runner_on_failed(self, host, res, ignore_errors=False):
        r_out = ""
        if isinstance(res, dict) and "msg" in res:
            r_out += res["msg"]
        self._result[host] = {"retcode": 1, "retout": r_out}

    def runner_on_unreachable(self, host, res):
        r_out = ""
        if isinstance(res, dict) and "msg" in res:
            r_out += res["msg"]
        self._result[host] = {"retcode": -1, "retout": r_out}


class ServiceStatusCallback(CallbackBase):
    def __init__(self):
        super(ServiceStatusCallback, self).__init__()
        self._result = {}

    def get_result(self):
        return self._result

    def runner_on_ok(self, host, res):
        running = 1
        if isinstance(res, dict) and "changed" in res and not res["changed"]:
            running = 0
        self._result[host] = {"retcode": running, "retout": ""}

    def runner_on_failed(self, host, res, ignore_errors=False):
        r_out = ""
        if isinstance(res, dict) and "msg" in res:
            r_out += res["msg"]
        self._result[host] = {"retcode": 1, "retout": r_out}

    def runner_on_unreachable(self, host, res):
        r_out = ""
        if isinstance(res, dict) and "msg" in res:
            r_out += res["msg"]
        self._result[host] = {"retcode": -1, "retout": r_out}


class ServiceCallback(CallbackBase):
    def __init__(self):
        super(ServiceCallback, self).__init__()
        self._result = {}

    def get_result(self):
        return self._result

    def runner_on_ok(self, host, res):
        self._result[host] = {"retcode": 0, "retout": ""}

    def runner_on_failed(self, host, res, ignore_errors=False):
        r_out = ""
        if isinstance(res, dict) and "msg" in res:
            r_out += res["msg"]
        self._result[host] = {"retcode": 1, "retout": r_out}

    def runner_on_unreachable(self, host, res):
        r_out = ""
        if isinstance(res, dict) and "msg" in res:
            r_out += res["msg"]
        self._result[host] = {"retcode": -1, "retout": r_out}


class AnsibleRunner(object):
    def __init__(self, module_name="", module_args=None, pattern="", forks=None, timeout=None, check=False):
        self._module_name = module_name
        self._module_args = module_args if module_args is not None else dict()
        self._pattern = pattern
        self._forks = forks
        self._timeout = timeout
        self._check = check

    def run(self, callback):
        # initialize needed objects
        variable_manager = VariableManager()
        loader = DataLoader()
        Options = namedtuple('Options', ['connection', 'module_path', 'timeout', 'forks',
                                         'become', 'become_method', 'become_user', 'check'])
        options = Options(connection='ssh', module_path=None, timeout=self._timeout, forks=self._forks,
                          become=None, become_method=None, become_user=None, check=self._check)
        passwords = dict(vault_pass='secret')

        # create inventory and pass to var manager
        inventory = Inventory(loader=loader, variable_manager=variable_manager)
        variable_manager.set_inventory(inventory)
        hosts = inventory.list_hosts(self._pattern)
        if len(hosts) == 0:
            return None

        # create play with tasks
        tasks = [dict(action=dict(module=self._module_name, args=self._module_args))]
        play_source = dict(hosts=self._pattern, gather_facts='no', tasks=tasks)
        play = Play().load(play_source, variable_manager=variable_manager, loader=loader)

        # actually run it
        tqm = None
        try:
            tqm = TaskQueueManager(inventory=inventory, variable_manager=variable_manager, loader=loader,
                                   options=options, passwords=passwords, stdout_callback=callback)
            tqm.run(play)
        finally:
            if tqm is not None:
                tqm.cleanup()


def list_hosts():
    inventory = Inventory(loader=DataLoader(), variable_manager=VariableManager())
    return [host.get_name() for host in inventory.list_hosts()]


def run_ping(pattern):
    ping_callback = PingCallback()
    runner = AnsibleRunner(module_name="ping", pattern=pattern)
    runner.run(ping_callback)

    return ping_callback.get_result()


def run_shell(pattern, cmd_line):
    options = {u'_raw_params': cmd_line}
    shell_callback = ShellCallback()
    runner = AnsibleRunner(module_name="shell", module_args=options, pattern=pattern)
    runner.run(shell_callback)

    return shell_callback.get_result()


def run_copy(pattern, src, dest):
    options = {"src": src, "dest": dest}
    copy_callback = CopyCallback()
    runner = AnsibleRunner(module_name="copy", module_args=options, pattern=pattern)
    runner.run(copy_callback)

    return copy_callback.get_result()


def run_service(pattern, service_name, action):
    check = False
    service_callback = ServiceCallback()
    options = {"name": service_name}
    if action == "status":
        options["state"] = "started"
        check = True
        service_callback = ServiceStatusCallback()
    elif action == "start":
        options["state"] = "started"
    elif action == "stop":
        options["state"] = "stopped"
    elif action == "restart":
        options["state"] = "restarted"
    elif action == "reload":
        options["state"] = "reloaded"
    elif action == "enable":
        options["enabled"] = "yes"
    elif action == "disable":
        options["enabled"] = "no"
    else:
        raise ValueError("action must be 'status', 'start', 'stop', 'restart', 'reload', 'enable' or 'disable'")

    runner = AnsibleRunner(module_name="service", module_args=options, pattern=pattern, check=check)
    runner.run(service_callback)

    return service_callback.get_result()


def run_service_status(pattern, service_name):
    return run_service(pattern, service_name, "status")


def run_service_start(pattern, service_name):
    return run_service(pattern, service_name, "start")


def run_service_stop(pattern, service_name):
    return run_service(pattern, service_name, "stop")


def run_service_restart(pattern, service_name):
    return run_service(pattern, service_name, "restart")


def run_service_reload(pattern, service_name):
    return run_service(pattern, service_name, "reload")


def run_service_enable(pattern, service_name):
    return run_service(pattern, service_name, "enable")


def run_service_disable(pattern, service_name):
    return run_service(pattern, service_name, "disable")
