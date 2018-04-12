"""
Library for libvirt_ci related helper functions and classes
"""
import logging
import errno
import fcntl
import json
import os
import platform
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import datetime
import yaml

import socket
import urllib2

# NOTE: Please don't import any third-party modules in this module
# This allowing installing libvirt-ci without any dependencies

from . import ansible

from libvirt_ci.data import KEY_PATH, RESOURCE_PATH, REPO_PATH
from libvirt_ci.config import CONFIG_PATH

LOGGER = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
class CmdResult(object):
    """
    A class representing the result of a system call.
    """

    def __init__(self, cmdline):
        self.cmdline = cmdline
        self.stdout = ""
        self.stdout_lines = []
        self.stderr = ""
        self.exit_code = None
        self.exit_status = "undefined"
        self.duration = 0.0

    def __str__(self):
        result = ''
        result += "command    : %s\n" % self.cmdline
        result += "exit_status: %s\n" % self.exit_status
        result += "exit_code  : %s\n" % self.exit_code
        result += "duration   : %s\n" % self.duration
        result += "stdout     :\n%s\n" % self.stdout
        result += "stderr     :\n%s\n" % self.stderr
        return result


class CmdError(Exception):
    """
    Exception class specifically used for `run` function
    """
    pass


def split(string):
    """
    Split a string from ',', spaces, or newlines to a list
    """
    return [e.strip() for e in re.split('[ ,\n]', string) if e.strip()]


def escape(in_str):
    """
    Escape a string for HTML use.
    """
    out_str = (isinstance(in_str, basestring) and in_str or '%s' % in_str)
    out_str = out_str.replace('&', '&amp;')
    out_str = out_str.replace('<', '&lt;')
    out_str = out_str.replace('>', '&gt;')
    out_str = out_str.replace('"', "&quot;")
    return out_str


def output(string):
    """
    Print a string to stdout and flush it from cache
    """
    sys.stdout.write(string)
    sys.stdout.flush()


def which(program):
    """
    Get the full path of a executable binary
    """
    def _is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, _ = os.path.split(program)
    if fpath:
        if _is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if _is_exe(exe_file):
                return exe_file

    return None


def run(cmdline, timeout=1200, debug=False, ignore_fail=True, host=None):
    """
    Run the command line and return the result with a CmdResult object.

    :param cmdline: The command line to run.
    :type cmdline: str.
    :param timeout: After which the calling processing is killed.
    :type timeout: float.
    :param debug: Enable debug
    :type debug: boolean
    :param ignore_fail: Ingnore fail if set as True
    :type ignore_fail: boolen
    :param host: Host name or ip, default to None
    :type host: str
    :returns: CmdResult -- the command result.
    :raises:
    """
    if host:
        result = run_playbook('remote_cmd',
                              hosts=host,
                              debug=debug,
                              private_key='libvirt-jenkins',
                              ignore_fail=ignore_fail,
                              remote=host,
                              cmd=cmdline,
                              timeout=timeout)
    else:
        result = run_local(cmdline, timeout=timeout,
                           debug=debug, ignore_fail=ignore_fail)
    return result


def run_local(cmdline, timeout=1200, debug=False, ignore_fail=True):
    """
    Run the command line and return the result with a CmdResult object.

    :param cmdline: The command line to run.
    :type cmdline: str.
    :param timeout: After which the calling processing is killed.
    :type timeout: float.
    :param debug: Enable debug
    :type debug: boolean
    :param ignore_fail: Ingnore fail if set as True
    :type ignore_fail: boolen
    :returns: CmdResult -- the command result.
    :raises:
    """
    def _collect_output(stream, tag):
        collector = ""
        try:
            lines = stream.read()
            if lines:
                collector += lines
                if debug:
                    for line in lines.splitlines():
                        LOGGER.info('[%s] %s', tag, line)
        except IOError as detail:
            if detail.errno != errno.EAGAIN:
                raise
        return collector

    def _update_result():
        done = False
        exit_code = process.poll()
        result.duration = (time.time() - start)

        select.select([process.stdout, process.stderr], [], [], 0.1)
        result.stdout += _collect_output(process.stdout, 'stdout')
        result.stderr += _collect_output(process.stderr, 'stderr')
        if exit_code is not None:
            result.exit_code = exit_code
            if exit_code == 0:
                result.exit_status = "success"
            else:
                result.exit_status = "failure"
            done = True

        if result.duration > timeout:
            done = True
        return done

    start = time.time()
    if debug:
        LOGGER.info('Running command "%s"', cmdline)
    process = subprocess.Popen(
        cmdline,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        preexec_fn=os.setsid,
    )

    fcntl.fcntl(
        process.stdout,
        fcntl.F_SETFL,
        fcntl.fcntl(process.stdout, fcntl.F_GETFL) | os.O_NONBLOCK,
    )
    fcntl.fcntl(
        process.stderr,
        fcntl.F_SETFL,
        fcntl.fcntl(process.stderr, fcntl.F_GETFL) | os.O_NONBLOCK,
    )

    result = CmdResult(cmdline)

    try:
        while True:
            if _update_result():
                return result
    finally:
        if result.exit_code is None:
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGKILL)
            result.exit_status = "timeout"
        if result.exit_status != 'success' and not ignore_fail:
            if result.exit_status == "failure":
                raise CmdError("Command Failed:\n%s" % result)
            elif result.exit_status == 'timeout':
                raise CmdError("Command Timed out:\n%s" % result)
            else:
                raise CmdError("Unknown Error:\n%s" % result)


def wait_for(func, timeout, first=0.0, step=1.0, text=None):
    """
    Wait until func() evaluates to True.

    If func() evaluates to True before timeout expires, return the
    value of func(). Otherwise return None.

    :param timeout: Timeout in seconds
    :param first: Time to sleep before first attempt
    :param steps: Time to sleep between attempts in seconds
    :param text: Text to print while waiting, for debug purposes
    """
    start_time = time.time()
    end_time = time.time() + float(timeout)

    time.sleep(first)

    while time.time() < end_time:
        if text:
            LOGGER.debug("%s (%f secs)", text, (time.time() - start_time))

        out = func()
        if out:
            return out

        time.sleep(step)

    return None


def restart_service(services, host=None):
    """
    Restart a bunch of services.
    """
    if isinstance(services, str):
        run('service %s restart' % services, host=host)
    elif isinstance(services, list):
        for service in services:
            run('service %s restart' % service, host=host)
    else:
        LOGGER.error("%s should be a str or list", services)


def get_arch(host=None):
    """
    Get the hardware architecture of the machine.
    """
    arch = run('/bin/uname -m', host=host).stdout.rstrip()
    if re.match(r'i\d86$', arch):
        arch = 'i386'
    return arch


def get_dist(host=None):
    """
    Get info of the Linux OS distribution"

    :param host: str, hostname
    :return: tuple, dist vendor, major, minor and id
    """
    if host:
        fact = collect_facts(hosts=host)[host]
        dist_vendor = fact['ansible_distribution'].lower()
        dist_version = fact['ansible_distribution_version']
        dist_id = fact['ansible_distribution_release']
        dist_kernel = fact['ansible_kernel']
    else:
        dist_vendor, dist_version, dist_id = platform.dist()
        dist_kernel = platform.release()
    # Both RHEL and RHEL-alt use the same codename now
    if int(dist_kernel.split('.')[0]) == 4 and dist_id == "Maipo":
        dist_id = "RHEL-ALT"

    try:
        dist_major, dist_minor = [int(n) for n in dist_version.split('.')]
    except ValueError:
        dist_major = int(dist_version)
        dist_minor = 0
    return (dist_vendor, dist_major, dist_minor, dist_id)


def determine_os_variant(vm_name):
    """
    Tries to determine the supported os variant from vm_name.
    """
    _, dist_major, _, _ = get_dist()
    if dist_major >= 7:
        query_cmd = 'osinfo-query --fields=short-id,name os'
    else:
        query_cmd = 'virt-install --os-variant list'
    os_variants = run(query_cmd).stdout
    os_patterns = [r"rhel\d+.?\d*", r"win\d+[.k]?\d?[r]?2?"]

    def _valid_variant(variant):
        return bool(re.search(r"%s" % variant, os_variants, re.MULTILINE))

    def _replace_variant(variant):
        if variant.startswith("win"):
            var_dict = {'2000': '2k', '2003': '2k3', '2008': '2k8'}
            for key in var_dict:
                if key in variant:
                    return variant.replace(key, var_dict[key])
        return variant

    os_variant = None
    for pat in os_patterns:
        os_variant = re.search(pat, vm_name, re.I)
        if os_variant:
            break

    if os_variant is None:
        LOGGER.warning("Can't determine os variant from name: %s", vm_name)
        return 'none'

    os_variant = _replace_variant(os_variant.group().lower())
    if _valid_variant(os_variant):
        return os_variant
    else:
        if os_variant.startswith('rhel'):
            default_rhel = "rhel7"
            if _valid_variant(os_variant[:5]):
                return os_variant[:5]
            else:
                return default_rhel
        if os_variant.startswith('win'):
            default_win = "win7"
            return default_win


def clean_vm(vm_name, uri=None, host=None):
    """
    Clean up specific VM name
    """
    cmd = 'virsh'
    if uri is not None:
        cmd += ' -c %s' % uri

    destroy_cmd = cmd + " destroy"
    undefine_cmd = cmd + " undefine --snapshots-metadata --managed-save "

    _, dist_major, dist_minor, _ = get_dist(host=host)
    if dist_major >= 7 and dist_minor >= 2 and (uri and 'lxc' not in uri):
        undefine_cmd += " --nvram"

    run(destroy_cmd + " " + vm_name, host=host)
    clean_vm_with_pid(vm_name, host=host)
    run(undefine_cmd + " " + vm_name, host=host)


def clean_vm_with_pid(vm_name, host=None):
    """
        Clean up specific VM name with pid
    """
    cmdline = 'ps -ef | grep qemu | grep guest=%s, | grep -v grep' % vm_name
    psstdout = run(cmdline, debug=True, host=host).stdout
    if psstdout:
        cmdline = 'kill -9 %s' % psstdout.split()[1]
        run(cmdline, debug=True, host=host)


def test_match(patt_str, test_str):
    """
    Test if a test name match with the name pattern.
    """
    patts = split(patt_str)
    for patt in patts:
        match = True
        segments = patt.split('..')
        items = test_str.split('.')
        idx = 0
        for segment in segments:
            seg_items = segment.split('.')
            try:
                while True:
                    idx = items.index(seg_items[0])
                    if items[idx:len(seg_items)] == seg_items:
                        items = items[len(seg_items):]
                        break
                    else:
                        del items[0]
            except ValueError:
                match = False
                break
        if match:
            return True
    return False


def format_inventory(hosts=None, user='root'):
    """
    Create inventory file for ansible

    :param hosts: list, str or dict of hostnames
    :param user: ssh user for connect
    :return: inventory file path and host name list tuple
    """
    if not isinstance(user, (str, unicode)):
        raise TypeError("Unsupported user type %s" % type(user))

    inventory_file = tempfile.NamedTemporaryFile(
        prefix='libvirt_ci-inventory-', delete=False)
    inventory_path = inventory_file.name

    host_list = []

    def _write_hosts(hosts):
        localhosts = ['localhost', '127.0.0.1']
        for host in hosts:
            conn = 'ssh'
            if host in localhosts:
                conn = 'local'
            line = "%s ansible_user=%s " % (host, user)
            line += "ansible_connection=%s\n" % conn
            inventory_file.write(line)

    # Using localhost if hosts not given
    if hosts is None:
        hosts = ['localhost']

    if isinstance(hosts, list):
        _write_hosts(hosts)
        host_list = hosts
    elif isinstance(hosts, dict):
        # pylint: disable=no-member
        for sec, val_hosts in hosts.items():
            inventory_file.write('[%s]\n' % sec)
            _write_hosts(val_hosts)
            inventory_file.write('\n')
            host_list.append(val_hosts)
    elif isinstance(hosts, (str, unicode)):
        # pylint: disable=no-member
        host_list = hosts.split(',')
        _write_hosts(host_list)

    else:
        raise TypeError("Unsupported hosts type %s" % type(hosts))

    inventory_file.close()
    return (inventory_path, host_list)


def collect_facts(hosts=None, user='root'):
    """
    Use ansible to collect host facts

    :param hosts: list, str, dict of hostnames
    :param user: ssh user
    :return: facts dict use hostname as key
    """
    inv_file, host_list = format_inventory(hosts, user)
    fact_path = '/tmp/fact_collect'
    cmd = 'ansible all -i %s -m setup --tree %s' % (inv_file, fact_path)
    run_local(cmd)
    fact_dict = {}
    for name in host_list:
        file_path = '%s/%s' % (fact_path, name)
        if os.path.exists(file_path):
            with open(file_path) as host_fact:
                fact_dict[name] = json.loads(host_fact.read()).get('ansible_facts')
                if not fact_dict[name]:
                    LOGGER.error('Empty Ansible Fact! Something is wrong.')
    os.remove(inv_file)
    shutil.rmtree(fact_path)
    return fact_dict


class AnsibleRunError(Exception):
    """
    Exception class indicates an ansible run is failed.
    """


def run_playbook(playbook, hosts=None, user=None, private_key=None, tags=None,
                 verbose=False, ignore_fail=False, extra_vars_file=None,
                 debug=False, **extra_vars):
    """
    Run ansible playbook on specified hosts with custom arguments

    :param playbook: The playbook name or path.
    :param hosts: str, the host name
    :param user: Ansible user.
    :param private_key: Ansible ssh private key name or path
    :param tags: Ansible tags
    :param verbose: Ansible verbosity option
    :param ignore_fail: Ignore fail when Ansible run failed
    :param extra_vars_file: Accept ansible var file if exist
    :param debug: Log debug info if enable
    :param extra_vars: dict for ansible extra vars
    :returns: CmdResult or ansible module return dict.
    :raises: AnsibleRunError

    """
    resource_dir = RESOURCE_PATH
    if not playbook.endswith(('.yaml', '.yml')):
        playbook_path = os.path.join(
            resource_dir, 'playbooks', playbook + '.yaml')
    else:
        playbook_path = os.path.join(
            resource_dir, 'playbooks', playbook)

    verbosity = 0
    ssh_args = None
    inventory_path = ''
    if user is None:
        user = 'root'
    try:
        inventory_path, host_list = format_inventory(hosts, user)
        if any('pok' in s for s in host_list):
            ssh_args = '-F %s' % os.path.join(
                CONFIG_PATH, 'ibm_pok_ssh_config')

        if private_key:
            private_key = os.path.join(KEY_PATH, private_key)
        if verbose:
            verbosity = 3
        if extra_vars_file:
            with open(extra_vars_file) as extra_vars_f:
                extra_vars.update(yaml.load(extra_vars_f))
        new_ans = ansible.Ansible(host_list=inventory_path,
                                  private_key=private_key,
                                  extra_vars=extra_vars,
                                  tags=tags,
                                  ssh_args=ssh_args,
                                  verbosity=verbosity)
        rc, result = new_ans.run_playbook(playbook_path)
        fail_msgs = ["Failed to retrive ansible result with:"]
        if rc:
            if 'cmd' not in result and extra_vars.get('cmd'):
                # Ansible result doesn't have 'cmd' on failure which is required by us
                result['cmd'] = extra_vars.get('cmd')
            if 'msg' in result:
                fail_msgs.append(result['msg'])
            elif 'stdout_lines' in result:
                for line in result['stdout_lines']:
                    match = re.search(r'fatal: \[.*\]: FAILED! => (.*)', line)
                    if match:
                        fatal_info = json.loads(match.group(1))
                        if 'stderr' in fatal_info:
                            for _line in fatal_info['stderr'].splitlines():
                                fail_msgs.append(_line)
                        if 'msg' in fatal_info:
                            fail_msgs.append(fatal_info['msg'])
            elif 'stderr_lines' in result:
                fail_msgs.extend(result['stderr_lines'])
            elif 'stderr' in result:
                fail_msgs.append(result['stderr'])
            elif 'exception' in result:
                fail_msgs.append(result['exception'])
            if not ignore_fail:
                raise AnsibleRunError('\n'.join(fail_msgs))
            LOGGER.error("Ansible job failed with result: %s", result)

        if debug and result:
            LOGGER.info("Ansilbe run result is %s:\n", result)

        # Only ansible command/shell module could be parsed with CmdResult
        if result and 'cmd' in result:
            res = CmdResult(result['cmd'])
            res.stdout = result.get('stdout', '')
            res.stdout_lines = result.get('stdout_lines') or fail_msgs
            res.stderr = result.get('stderr') or '\n'.join(fail_msgs)
            time_str = result.get('delta', '00:00:00.0000').split(',')[-1].strip()
            delta = datetime.datetime.strptime(time_str, '%H:%M:%S.%f')
            res.duration = delta.second + delta.minute * 60
            res.duration += delta.hour * 3600
            res.duration += float(delta.microsecond) / 1000000
            res.exit_code = int(result.get('rc', rc))
            return res

        return result
    finally:
        try:
            os.remove(inventory_path)
        except (OSError, IOError):
            pass


def query_yes_no(question, default="yes"):
    """
    Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
    It must be "yes" (the default), "no" or None (meaning an answer
    is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def diff_dict(dict_old, dict_new):
    """
    Dict compare
    """
    dict_old = set(dict_old)
    dict_new = set(dict_new)
    created = dict_new - dict_old
    deleted = dict_old - dict_new
    shared = dict_old & dict_new
    return created, deleted, shared


def split_repo_line(line):
    """
    Split a line format as "url branch[:commit]" to a
    (url, branch, commit) tuple.
    """
    repo_url, branch = line.split()

    commit = None
    if ':' in branch:
        branch, commit = branch.split(':', 1)

    return repo_url, branch, commit


def update_git_repo(repo_name, repo_url, branch=None, commit=None):
    """
    Create/Update git repo stored in libvirt_ci data path
    Should be at /var/lib/libvirt_ci/repos/<repo>
    """
    repo_dir = os.path.join(REPO_PATH, repo_name)
    if os.path.exists(repo_dir):
        LOGGER.info('Updating repo %s', repo_name)

        old_path = os.getcwd()
        try:
            os.chdir(repo_dir)
            if branch:
                run('git checkout %s' % branch, debug=True)
            run('git pull', debug=True)
        finally:
            os.chdir(old_path)
    else:
        LOGGER.info("Retrieving %s from %s", repo_name, repo_url)

        cmd = 'git clone --quiet %s %s' % (
            repo_url, repo_dir)
        if branch:
            cmd += ' --branch %s' % branch
        # TODO: remove this work around
        if repo_name == 'autotest':
            cmd = cmd + ' --recursive'
        for _ in range(3):
            result = run(cmd, debug=True)
            if result.exit_status == 'success':
                break
            else:
                LOGGER.info("Cloning %s failed", repo_name)
                time.sleep(5)

    # Reset to specific commit/tag
    if commit:
        LOGGER.info("Resetting HEAD of %s to %s", repo_name, commit)
        old_path = os.getcwd()
        try:
            os.chdir(repo_dir)
            run('git reset --hard %s' % commit)
        finally:
            os.chdir(old_path)


def check_set_gservice_broker():

    SNIPROXIES = [
        "10.8.241.45",
    ]

    GDOMAINS = [
        "clients3.google.com",
        "www.google.com",
        "accounts.google.com",
        "docs.google.com",
        "spreadsheets.google.com",
    ]

    _orig_getaddrinfo = socket.getaddrinfo
    _orig_connect = socket.socket.connect

    # pylint: disable=no-member,broad-except
    for proxy in SNIPROXIES + [None]:
        try:
            urllib2.urlopen("http://clients3.google.com/generate_204",
                            timeout=60).read()
        except Exception:
            if proxy:
                LOGGER.info("G service not avaliable, using proxy %s", proxy)
                setattr(socket, '__sniproxy__', proxy)

                def ggetaddrinfo(*args, **kwargs):
                    host, port = args[0], args[1]
                    if host in GDOMAINS:
                        return [(2, 1, 6, '', (socket.__sniproxy__, port)), ]
                    else:
                        return _orig_getaddrinfo(*args, **kwargs)

                def gconnect(self, *args, **kwargs):
                    if isinstance(args[0], tuple):
                        host, port = args[0]
                        if host in GDOMAINS:
                            args = ((socket.__sniproxy__, port),)
                    return _orig_connect(self, *args, **kwargs)

                socket.getaddrinfo = ggetaddrinfo
                socket.socket.connect = gconnect

            else:
                LOGGER.error("G service seems not avaliable, and "
                             "we don't have more proxy to try!")
                socket.getaddrinfo = _orig_getaddrinfo
                socket.socket.connect = _orig_connect


def all_leaf_class(cls):
    """
    Consider class inherites like a tree, consider only the leaf as
    valid classes
    """
    def _all_leaf(cls):
        subs = cls.__subclasses__()
        return sum([_all_leaf(cls_) for cls_ in subs], []) if subs else [cls]

    if cls.__subclasses__():
        return _all_leaf(cls)
    return []


def ssh_copy_id(remote_user, remote_host):
    """
    Copyt SSH public key to perform SSH login without password
    """
    ssh_dir = os.path.join(os.getenv("HOME"), '.ssh')
    if 'id_rsa' not in os.listdir(ssh_dir):
        subprocess.call('ssh-kengen', shell=True)
    subprocess.call('ssh-copy-id %s@%s' %
                    (remote_user, remote_host), shell=True)
