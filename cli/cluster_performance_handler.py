#!/usr/bin/python
# coding:utf-8

import commands
# from icfs_util import get_remote_host_list
import datetime
import json
import os
import sqlite3
import sys
import threading
import time
import signal
from icfs_util import run_local_cmd
import icfs_log
import OptParser
import re
import paramiko
from threading import Thread
from multiprocessing import Process
import ctypes
import inspect
import binascii

log = icfs_log.get_log("cluster_performance_handler")
DEBUG = 0


def _async_raise(tid, exctype):
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res == 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


def main():
    class MonitorTime(object):
        time_format = "%Y-%m-%d %H:%M:%S"
        patt = re.compile("\d+-\d+-\d+\s+\d+:\d+:(00|15|30|45)")

        def __init__(self):
            self.record_time = datetime.datetime.now().strftime(self.time_format)

        def match(self):
            m = self.patt.match(self.record_time)
            if m:
                return True
            else:
                return False


    class Chan(object):
        def __init__(self, chan):
            self.chan = chan
            self.chan.invoke_shell()
            self.status = 0
            self._lock = threading.Lock()
            self.data_avail = True

        def acquire(self):
            self._lock.acquire()
            try:
                if not self.is_using():
                    self.status +=1
                    return self.chan
                else:
                    return None
            finally:
                self._lock.release()

        def is_using(self):
            if self.status == 0:
                return False
            return True

        def get_data_avail(self):
            return self.data_avail

        def set_data_avail(self, is_useable):
            self.data_avail = is_useable

        def release(self):
            self._lock.acquire()
            try:
                self.status = 0
            finally:
                self._lock.release()


    class SshConnect(object):
        port = 22
        username = "root"
        timeout = 5
        parallel_number_max = 9
        execute_number_max = 20

        def __init__(self, tgt):
            # self.status: ['free', 'busy', 'unusable']
            self.host = tgt
            self.ssh = paramiko.SSHClient()
            self.ssh.load_system_host_keys()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.parallel_number = 0
            self.lock = threading.Lock()
            self.execute_count = 0
            self.chan = list()

        def connect(self, timeout=None):
            if timeout is None:
                timeout = self.timeout

            self.lock.acquire()
            try:
                self.ssh.connect(hostname=self.host, port=self.port, username=self.username, timeout=timeout)
                log.info("connect [host:%s] [port:%s] [username:%s] [session_id:%s]" %
                         (self.host, self.port, self.username, binascii.b2a_hex(self.ssh.get_transport().session_id)))
                for i in range(self.parallel_number_max):
                    self.chan.append(Chan(self.ssh.get_transport().open_session()))
            except Exception:
                self.parallel_number = -100
                self.lock.release()
                return False

            self.parallel_number = 0
            self.execute_count = 0
            self.lock.release()
            return True

        def close(self):
            self.lock.acquire()
            self.parallel_number = -100
            self.ssh.close()
            self.lock.release()

        def execute_num_increase(self):
            self.execute_count += 1

        def parallel_num_increase(self):
            self.parallel_number += 1

        def parallel_num_reduce(self):
            if self.parallel_number > 0:
                self.parallel_number -= 1

        def counting(func):
            def wrapper(self, *args, **kwargs):
                result = func(self, *args, **kwargs)
                self.lock.acquire()
                self.execute_num_increase()
                self.parallel_num_reduce()
                self.lock.release()

                return result
            return wrapper

        def ask_for_chan(self):
            for item in self.chan:
                if item.acquire() is not None:
                    return item

            return None

        @counting
        def run_remote_cmd(self, cmd, timeout=None):
            retcode = 0
            stdout = ''
            stderr = ''
            chan = self.ask_for_chan()
            if chan is None:
                retcode = 1
                stderr = 'unable to get channel'
                return {self.host: {'retcode': retcode, 'stdout': stdout, 'stderr': stderr}}
            channel = chan.chan
            try:
                try:
                    channel.settimeout(timeout)
                    is_avail = chan.get_data_avail()
                    if is_avail:
                        channel.send(cmd + '\n')
                        recv = channel.recv(2048)
                        chan.set_data_avail(True)
                        stdout += recv
                        stdout = stdout.strip()
                    else:
                        channel.recv(2048)
                        chan.set_data_avail(True)
                        retcode = 1
                        stderr = 'Error(054): Failed to run command on remote hosts'
                        return {self.host: {'retcode': retcode, 'stdout': stdout, 'stderr': stderr}}
                except Exception:
                    chan.set_data_avail(False)
                    retcode = 1
                    stderr = 'Error(054): Failed to run command on remote hosts'
                    return {self.host: {'retcode': retcode, 'stdout': stdout, 'stderr': stderr}}

                return {self.host: {'retcode': retcode, 'stdout': stdout, 'stderr': stderr}}
            finally:
                chan.release()

        def is_available(self):
            if (self.parallel_number < self.parallel_number_max) \
                    and (self.parallel_number >= 0):
                return True
            else:
                return False

        def ask_for_self(self):
            self.lock.acquire()
            if self.is_available():
                self.parallel_num_increase()
                self.lock.release()
                return self
            else:
                self.lock.release()
                return None

        def is_need_to_destroy(self):
            if self.parallel_number == -1:
                return True
            else:
                return False

        def is_need_to_reconnect(self):
            return False
            if self.execute_count >= self.execute_number_max:
                return True
            else:
                return False

        def reconnect(self):
            self.close()
            connect = self.connect()

            return connect

        def is_active(self):
            try:
                return self.ssh.get_transport().active
            except AttributeError:
                return False


    class LocalConnection(object):
        def __init__(self, tgt):
            self.host = tgt

        def connect(self):
            return True

        def close(self):
            pass

        def parallel_num_increase(self):
            pass

        def parallel_num_reduce(self):
            pass

        def parallel_num_reduce(self):
            pass

        def run_remote_cmd(self, cmd, timeout=None):
            status, output = commands.getstatusoutput(cmd)
            return {self.host: {'retcode': status, 'stdout': output, 'stderr': ''}}

        def is_available(self):
            return self

        def ask_for_self(self):
            return True

        def is_need_to_destroy(self):
            return False

        def is_need_to_reconnect(self):
            return False

        def reconnect(self):
            self.close()
            connect = self.connect()

            return connect

        def is_active(self):
            return True


    class LocalHost(object):
        def __init__(self, hostname):
            self.hostname = hostname
            self.active_connect = list()

        def add_active_connect(self, local_connect=None):
            if self.active_connect:
                return None
            else:
                local_connect = LocalConnection(self.hostname)
                self.active_connect.append(local_connect)

        def remove_active_connect(self, local_connect):
            try:
                self.active_connect.remove(local_connect)
            except ValueError:
                pass

        def init_ssh_pool(self):
            self.add_active_connect()

        def init_loop(self, host_list):
            if self.hostname in host_list:
                self.init_ssh_pool()
                return True
            else:
                self.close()
                del self.active_connect[:]
                return False

        def ask_for_ssh_connect(self):
            return self.active_connect[0]

        def close(self):
            pass


    class RemoteHost(object):
        ssh_pool_max = 4
        ssh_pool_min = 3
        def __init__(self, hostname):
            self.hostname = hostname
            self.active_connect = list()
            self.not_active_connect = list()
            self.lock = threading.Lock()
            self.normal_count = 0

        def add_active_connect(self, ssh_connect=None, timeout=None):
            if ssh_connect is None:
                ssh_connect = SshConnect(self.hostname)
                connect = ssh_connect.connect(timeout)
            else:
                connect = True

            if connect:
                self.active_connect.append(ssh_connect)
                return ssh_connect
            else:
                return None

        def remove_active_connect(self, ssh_connect):
            try:
                self.active_connect.remove(ssh_connect)
            except ValueError:
                pass

        def init_ssh_pool(self):
            for i in range(self.ssh_pool_min):
                self.add_active_connect()

            num = self.ssh_pool_min - len(self.active_connect)
            if num > 0:
                log.error("Failed to initialize the connection to %s(%s) when the service starts" % (self.hostname, num))

        def init_loop(self, host_list):
            self.lock.acquire()
            try:
                if self.hostname in host_list:
                    for ssh_connect in self.active_connect:
                        if ssh_connect.is_need_to_reconnect():
                            connect = ssh_connect.reconnect()
                            if connect:
                                pass
                            else:
                                ssh_connect.close()
                                self.not_active_connect.append(ssh_connect)
                                continue

                        if not ssh_connect.is_active():
                            ssh_connect.close()
                            self.not_active_connect.append(ssh_connect)
                            continue

                    for ssh_connect in self.not_active_connect:
                        log.info("[hostname: %s] [init loop] [remove not active connection]" % self.hostname)
                        self.remove_active_connect(ssh_connect)

                    num = self.ssh_pool_min - len(self.active_connect)

                    if self.active_connect or (self.normal_count >= 4):
                        self.normal_count = 0
                        if num > 0:
                            for i in range(num):
                                result = self.add_active_connect(timeout=2)
                                if result is None:
                                    break
                                else:
                                    log.info("[hostname: %s] [init loop] [add new connection]" % self.hostname)
                    else:
                        self.normal_count += 1

                    del self.not_active_connect[:]
                    return True
                else:
                    self.normal_count = 0
                    self.close()
                    del self.active_connect[:]
                    del self.not_active_connect[:]
                    return False
            finally:
                self.lock.release()

        def ask_for_ssh_connect(self):
            self.lock.acquire()
            for ssh_connect in self.active_connect:
                if ssh_connect.ask_for_self():
                    self.lock.release()
                    return ssh_connect

            result = None

            if self.active_connect:
                num = self.ssh_pool_max - len(self.active_connect)
                if num > 0:
                    ssh_connect = self.add_active_connect(timeout=2)
                    if ssh_connect is not None:
                        log.info("[hostname: %s] [ask for ssh connect] [add new connection]" % self.hostname)
                        result = ssh_connect
                    else:
                        log.error("[hostname: %s] [ask for ssh connect] [add new connection]" % self.hostname)
                        pass  # result = None
                else:
                    pass    # result = None

            else:
                pass    # result = None

            self.lock.release()
            return result

        def close(self):
            self.normal_count = 0
            for ssh_connect in self.active_connect:
                ssh_connect.close()
            del self.active_connect[:]
            for ssh_connect in self.not_active_connect:
                ssh_connect.close()
            del self.not_active_connect[:]


    class Share(object):
        CONTROL = True

        def __init__(self):
            self.ssh_pool = dict()
            self.hostname_list = self.get_hostname_list()
            self.host = self.get_local_host()
            self.lock = threading.Lock()

        def init_ssh_pool(self):
            for hostname in self.hostname_list:
                if self.host == hostname:
                    self.ssh_pool[hostname] = LocalHost(hostname)
                else:
                    self.ssh_pool[hostname] = RemoteHost(hostname)

            for key, value in self.ssh_pool.iteritems():
                value.init_ssh_pool()

        def close(self):
            for hostname, ssh_pool in self.ssh_pool.iteritems():
                    ssh_pool.close()

            self.ssh_pool.clear()

        def ask_for_ssh_connect(self, hostname):
            try:
                ssh_pool = self.ssh_pool[hostname]
            except KeyError:
                return None

            return ssh_pool.ask_for_ssh_connect()

        def init_loop(self):
            new_hostname_list = self.get_hostname_list()
            new_host = self.get_local_host()

            self.hostname_list = self.ssh_pool.keys()
            for hostname in self.hostname_list:
                self.ssh_pool[hostname].init_loop(new_hostname_list)
                if hostname not in new_hostname_list:
                    log.info("[share] [init loop] [remove node: %s]" % hostname)
                    self.ssh_pool.pop(hostname)
                    continue

            for hostname in new_hostname_list:
                if hostname not in self.hostname_list:
                    if new_host == hostname:
                        log.info("[share] [init loop] [add local node: %s]" % hostname)
                        local_host = LocalHost(hostname)
                        local_host.init_ssh_pool()
                        self.ssh_pool[hostname] = local_host
                    else:
                        log.info("[share] [init loop] [add remote node: %s]" % hostname)
                        remote_host = RemoteHost(hostname)
                        remote_host.init_ssh_pool()
                        self.ssh_pool[hostname] = remote_host

            self.host = new_host
            self.hostname_list = new_hostname_list

        @staticmethod
        def get_hostname_list():
            hostname = []
            pattern1 = re.compile(r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([\S]+?)(\s*(?:#.*?)?|#.*?)$")
            pattern2 = re.compile(r"^\s*((?:[a-fA-F0-9]{0,4}:){0,7}[a-fA-F0-9]{0,4})\s+([\S]+?)(\s*(?:#.*?)?|#.*?)$")
            try:
                with open("/etc/hosts", "r") as fp:
                    lines = fp.readlines()
            except IOError:
                return hostname
            for line in lines:
                m1 = pattern1.match(line)
                m2 = pattern2.match(line)
                if m1 is not None:
                    host_name = m1.group(2)
                elif m2 is not None:
                    host_name = m2.group(2)
                else:
                    continue

                if host_name == 'localhost localhost.localdomain localhost4 localhost4.localdomain4':
                    continue
                if host_name == 'localhost localhost.localdomain localhost6 localhost6.localdomain6':
                    continue
                if "#" in host_name:
                    host_name = host_name.split("#")[0]
                if host_name == "":
                    continue
                hostname.append(host_name)
            return hostname

        @staticmethod
        def get_local_host():
            try:
                with open("/etc/hostname", "r") as fpRead:
                    host = fpRead.read().rstrip("\n")
            except IOError:
                return None

            return host


    class ClusterMonitor(Thread):
        max_exist_num = 4

        def __init__(self, share, record_time):
            Thread.__init__(self)
            self.count = 0
            self.share = share
            self.record_time = record_time

        def run(self):
            self.count_increase()
            cluster_collect_and_write_data(self.share, self.record_time)
            self.count = -1

        def is_normal_end(self):
            if self.count == -1:
                return True
            else:
                return False

        def is_still_not_run(self):
            if self.count == 0:
                return True
            else:
                return False

        def count_increase(self):
            if self.count != -1:
                self.count += 1

        def is_need_to_be_stopped(self):
            if self.max_exist_num is None:
                return False
            elif self.count == -1:
                return False
            elif self.count < self.max_exist_num:
                return False
            else:
                return True

        def stop_thread(self):
            try:
                _async_raise(self.ident, SystemExit)
            except Exception:
                pass


    class NodeMonitor(Process):
        def __init__(self):
            Process.__init__(self)

        def run(self):
            log.info("start node monitor")
            while True:
                monitor_time = MonitorTime()
                while not monitor_time.match():
                    monitor_time = MonitorTime()
                    continue
                cmd = "timeout -k 1 20 /usr/bin/node_performance_handler record" + " 2>&1 >>/dev/null &"
                os.system(cmd)
                time.sleep(14)


    class CleanSystemSession(Process):
        interval = 5760
        def __init__(self):
            Process.__init__(self)
            self.count = 0

        def loop(self):
            if self.count > self.interval:
                self.count = 0
            else:
                self.count += 1

            if self.count == 10:
                if not self.is_alive():
                    self.run()

        def run(self):
            log.info("start clean abandoned session")
            patt = re.compile("\s*session-(\d+)\.scope\s*.*?")
            cmd_query = "systemctl list-units | grep abandoned"
            output = commands.getoutput(cmd_query)
            lines = output.splitlines()
            for line in lines:
                m = patt.match(line)
                if m:
                    session_id = m.groups()[0]
                    cmd_stop = "loginctl terminate-session %s" % session_id
                    os.system(cmd_stop)
            log.info("end clean abandoned session")


    class MonitorService(object):
        loop_time = 15

        def __init__(self):
            self.cluster_monitor_dict = dict()
            self.share = Share()
            self.count = 0
            self.is_not_master_count = 0

            self.node_monitor = NodeMonitor()

            self.clean_system_session = CleanSystemSession()

        def loop_assert(self):
            try:
                if self.count >= 4:
                    is_master = self.if_this_node_is_master()
                    if is_master:
                        self.count = 0
                        self.is_not_master_count = 0
                        return True
                    else:
                        self.is_not_master_count += 1
                        if self.is_not_master_count >= 4:
                            self.count = 0
                            self.is_not_master_count = 0
                            return False
                        else:
                            return True
                else:
                    return True
            finally:
                self.count += 1


        @staticmethod
        def if_this_node_is_master():
            ret = run_local_cmd("icfs quorum_status -f json 2>/dev/null", timeout=10)
            if ret["retcode"]:
                return False

            status_json = ret['stdout'].strip()
            try:
                status = json.loads(status_json)
                quorum_leader_name = status["quorum_leader_name"]
            except Exception:
                return False

            # get current host name
            ret = run_local_cmd("hostname")
            if ret["retcode"]:
                return False
            hostname = ret['stdout'].strip()

            return hostname == quorum_leader_name

        def start(self):
            Share.CONTROL = True
            log.info("monitor service start")
            if not self.node_monitor.is_alive():
                self.node_monitor.start()

            while Share.CONTROL:
                is_master = self.if_this_node_is_master()
                if is_master:
                    log.info("the node is master mon node now")
                    self.cluster_start()
                else:
                    time.sleep(self.loop_time * 4)

                if not self.node_monitor.is_alive():
                    self.node_monitor.start()

                self.clean_system_session.loop()

        def cluster_start(self):

            self.share.init_ssh_pool()

            log.info("start cluster monitor")
            while Share.CONTROL:
                monitor_time = MonitorTime()
                while not monitor_time.match():
                    monitor_time = MonitorTime()
                    continue

                self.cluster_monitor_dict[monitor_time.record_time] = ClusterMonitor(self.share, monitor_time.record_time)

                for record_time, cluster_monitor in self.cluster_monitor_dict.iteritems():
                    if cluster_monitor.is_still_not_run():
                        cluster_monitor.start()
                    elif cluster_monitor.is_need_to_be_stopped():
                        cluster_monitor.stop_thread()
                        log.error("the single cluster monitor [%s] timeout" % record_time)
                    else:
                        cluster_monitor.count_increase()

                for record_time, cluster_monitor in self.cluster_monitor_dict.items():
                    if not cluster_monitor.is_alive():
                        cluster_monitor = self.cluster_monitor_dict.pop(record_time)
                        if not cluster_monitor.is_normal_end():
                            log.error(
                                "The record thread cluster_performance_handler %s exits abnormally" % record_time)

                self.share.init_loop()
                is_master = self.loop_assert()
                if not is_master:
                    log.info("the node is no longer the master node after four tests")
                    log.info("stop cluster monitor, re-enter the service loop")
                    self.stop(is_stop_node=False)
                    self.share = Share()
                    Share.CONTROL = True
                    break

                if not self.node_monitor.is_alive():
                    log.info("the node monitor aborted, now the node monitor is about to start again")
                    self.node_monitor.start()

                self.clean_system_session.loop()

                old_time = datetime.datetime.strptime(monitor_time.record_time, MonitorTime.time_format)
                now_time = datetime.datetime.now()
                interval = now_time - old_time
                interval = interval.seconds + 1
                if interval < 13:
                    time.sleep(self.loop_time - 2 - interval)
                elif interval < self.loop_time:
                    pass
                else:
                    count = interval / self.loop_time
                    log.error("The program skips %s records from %s + %s" % (count, old_time, self.loop_time))

        def reset(self):
            log.info("stop cluster monitor, re-enter the service loop")
            self.stop(is_stop_node=False)
            Share.CONTROL = True
            self.start()

        def stop(self, is_stop_node=True):
            if is_stop_node:
                log.info("monitor service stop")
            if is_stop_node:
                if self.node_monitor.is_alive():
                    os.kill(self.node_monitor.pid, signal.SIGKILL)

                if self.clean_system_session.is_alive():
                    os.kill(self.clean_system_session.pid, signal.SIGKILL)

            Share.CONTROL = False
            for record_time, cluster_monitor in self.cluster_monitor_dict.items():
                if cluster_monitor.is_alive():
                    cluster_monitor.stop_thread()
                    log.info("Monitor service is stopped, send SIGTERM to %s" % cluster_monitor.ident)
            self.share.close()
            if is_stop_node:
                sys.exit(6)

        def restart(self):
            log.info("the node is restarting the service")
            self.stop()
            os.system("/usr/bin/python /usr/bin/cluster_performance_handler.py record 2>&1 > /dev/null")
            log.info("the node completes service restart")

    service = MonitorService()


    def sighup(signum, frame):
        service.restart()

    def sigterm(signum, frame):
        service.stop()

    # handle signal SIGHUB
    signal.signal(signal.SIGHUP, sighup)

    # handle signal SIGTERM
    signal.signal(signal.SIGTERM, sigterm)

    service.start()


def chang_unit(data):
    data = data.upper()
    try:
        data = float(data)
        return data
    except (TypeError, ValueError):
        if data[-1] == "B":
            unit = 1
        elif data[-1] == "K":
            unit = 1024
        elif data[-1] == "M":
            unit = 1024 * 1024
        elif data[-1] == "G":
            unit = 1024 * 1024 * 1024
        elif data[-1] == "T":
            unit = 1024 * 1024 * 1024 * 1024
        elif data[-1] == "P":
            unit = 1024 * 1024 * 1024 * 1024 * 1024
        elif data[-1] == "E":
            unit = 1024 * 1024 * 1024 * 1024 * 1024 * 1024
        else:
            print "Error(610): Invalid input! " + str(data) + "  is error"
            sys.exit(1)
    try:
        data = float(data[0:-2])
    except (TypeError, ValueError):
        print "Error(610): Invalid input!  type error"
        sys.exit(1)
    data *= unit
    return data


def unit_convert(n):
    try:
        symbols = ('KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
        prefix = {}
        for i, s in enumerate(symbols):
            prefix[s] = 1 << (i + 1) * 10
        for s in reversed(symbols):
            if n >= prefix[s]:
                value = float(n) / prefix[s]
                return '%.1f %s' % (value, s)
        return "%s B" % n
    except (ValueError, TypeError), err:
        print err
        sys.exit(1)


def connect_db(db_name):
    # check if the dir is exit
    con = None
    if not os.path.exists("/dev/shm/cli/"):
        ret = run_local_cmd("mkdir -p /dev/shm/cli/")
        if ret["retcode"]:
            print "Error(3511): make dir /dev/shm/cli/ to store db fail, fail info %s!" % (ret['stdout']+ret["stderr"])
            sys.exit(1)
    try:
        con = sqlite3.connect("/dev/shm/cli/%s" % db_name)
    except Exception, err:
        print err
        sys.exit(1)
    return con


def get_hostname_list():
    hostname = []
    pattern = re.compile(r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([\S]+?)(\s*(?:#.*?)?|#.*?)$")
    try:
        with open("/etc/hosts", "r") as fp:
            lines = fp.readlines()
    except IOError:
        return hostname

    for line in lines:
        m = pattern.match(line)
        if m is None:
            continue
        if m.group(2) == 'localhost localhost.localdomain localhost4 localhost4.localdomain4':
            continue
        hostname.append(m.group(2).strip())

    return hostname


def _check_table(cur, table_name):
    try:
        crete_table_sql = '''CREATE TABLE IF NOT EXISTS %s(id integer primary key,
                                                                        record_time DATETIME NOT NULL,
                                                                        device TEXT NOT NULL,
                                                                        device_throughput TEXT NOT NULL)''' % table_name
        cur.execute(crete_table_sql)
    except Exception, err:
        print err
        sys.exit(1)


def save_perf_data(cur, device, data_time, value, table_name):
    try:
        # delete the data before 1 hour
        cur.execute("delete from %s where record_time < datetime('now', 'localtime', '-1 hours');" % table_name)
        # _check_table(cur, table_name)
        cur.execute("INSERT INTO %s (record_time, device, device_throughput) VALUES (?, ?, ?)" % table_name,
                    (data_time, device, str(value)))
    except Exception, err:
        if "no such table" in str(err):
            _check_table(cur, table_name)
            cur.execute("INSERT INTO %s (record_time, device, device_throughput) VALUES (?, ?, ?)" % table_name,
                        (data_time, device, str(value)))
        else:
            print err


def error(num, *args):
    if num == 610:
        print "Error(610): Invalid input!"
    elif num == 3504:
        print "Error(3504): get IO state fail, info: %s" % args[0]
    elif num == 3500:
        print "Error(3500): the object type %s not in query level %s" % (args[0], args[1])
    elif num == 3501:
        print "Error(3501): the input object code %s is invalid!" % args[0]
    elif num == 3502:
        print"Error(3502): the input node %s is not in cluster!" % args[0]
    elif num == 3503:
        print("Error(3503): only node level need level_value!")
    elif num == 3506:
        print("Error(3506): only support query history performance data in 1 hour!")
    elif num == 3507:
        print("Error(3507): invalid json format value %s!" % args[0])
    elif num == 3508:
        print("Error(3508): get data from remote %s fail, fail info: %s!" % (args[0], args[1]))
    # sys.exit(1)


def run_remote_cmd(tgt, cmd, share=None):
    try:
        ret_dict = {}
        if share is None:
            status, output = commands.getstatusoutput("ssh -o ConnectTimeout=2 -o ConnectionAttempts=2 -o PasswordAuthentication=no \
                                      -o StrictHostKeyChecking=no -o GSSAPIAuthentication=no \
                                      'root@%s' \"%s\"" % (tgt, cmd))
            ret_dict[tgt] = {"retcode": status, "stdout": output, "stderr": ""}
            return ret_dict
        else:
            ssh_connect = share.ask_for_ssh_connect(tgt)
            if ssh_connect is None:
                ret_dict[tgt] = {"retcode": 1, "stdout": "", "stderr": "unable to get connection"}
            else:
                ret_dict = ssh_connect.run_remote_cmd(cmd)

            return ret_dict
    except Exception, err:
        print "Error(054): Failed to run command on remote hosts"
        print err
        sys.exit(1)


def if_this_node_is_master():
    # get the master node name
    ret = run_local_cmd("icfs quorum_status -f json 2>/dev/null")
    if ret["retcode"]:
        print "Error(3509): get icfs quorum_status fail, fail info %s" % (ret["stdout"]+ret["stderr"])
        sys.exit(1)
    status_json = ret['stdout'].strip()
    status = json.loads(status_json)
    quorum_leader_name = status["quorum_leader_name"]
    # get current host name
    ret = run_local_cmd("hostname")
    if ret["retcode"]:
        print "Error(3510): get hostname fail, fail info %s" % (ret["stdout"]+ret["stderr"])
        sys.exit(1)
    hostname = ret['stdout'].strip()
    if DEBUG:
        print 'hostname %s, quorum_leader_name %s' % (hostname, quorum_leader_name)
    return hostname == quorum_leader_name


def get_data_from_remote(data_type, share=None, write_time=None):
    data_list = []
    unit = ''
    # get current date, for wait the node execute so the time will backward 8s
    current_date = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime(time.time()-8))
    # to wait node execute complete
    # time.sleep(8)
    # get host list
    hosts = get_hostname_list()
    if DEBUG:
        print hosts
    for item in hosts:
        # get nfs bandwidth
        ret = run_remote_cmd(item, "node_performance_handler node_%s %s" %
                             (data_type, current_date), share)
        if DEBUG:
            print "%s: python /usr/bin/node_performance_handler node_%s %s" % (item, data_type, current_date)
        if not ret[item]["retcode"]:
            if DEBUG:
                print ret[item]["stdout"]
            if len(ret[item]["stdout"].split("\n")) > 2:
                unit = ret[item]["stdout"].split("\n")[2].split(":")[-1].split()[1]
                if unit != 'ms' and unit != 'num' and unit != 'us' and unit != 'B' and unit != 'times':
                    data = ret[item]["stdout"].split("\n")[2].split(":")[-1].replace(' ', '')[0:-1]
                    print data
                    # transfer the unit
                    data = chang_unit(data)
                else:
                    data = ret[item]["stdout"].split("\n")[2].split(":")[-1].split()[0]
                data_list.append(float(data))
            else:
                data_list.append(0.0)
        else:
            print ret[item]["stderr"] + ret[item]["stdout"]
            # print >> sys.stderr, ret[item]["stderr"]
            # sys.exit(0)
    # print "data_list sum %f" % sum(data_list)
    return sum(data_list), unit


def write_data_to_db(db_name, table_name, data):
    con = None
    try:
        con = connect_db(db_name)
        cur = con.cursor()
        save_perf_data(cur, data["device"], data["time"], data["value"], table_name)
    except Exception, err:
        print err
        sys.exit(1)
    finally:
        if con:
            con.commit()
            con.close()


def put_data(data_type, db_name, write_time, share=None):
    # print os.getpid()
    data_write = {}
    begin_time = None
    if DEBUG:
        begin_time = time.time()
    value, unit = get_data_from_remote(data_type, share, write_time)
    if unit != 'ms' and unit != 'num' and unit != 'us' and unit != 'times' and unit != '%':
        # transfer the unit from B to other
        original_data = unit_convert(value)
    else:
        original_data = str(value) + ' ' + unit
    data_write["device"] = data_type.split("_")[-1]
    data_write["time"] = write_time
    data_write["value"] = original_data
    write_data_to_db(db_name, data_type, data_write)


def timeout_handler(signum, frame):
    os.kill(os.getpid(), signal.SIGTERM)
    print "Error(553): Unknown error"
    print "timeout"
    sys.exit(1)


class ClusterRecord(threading.Thread):
    def __init__(self, monitor_item, db_name, write_time, share=None):
        super(ClusterRecord, self).__init__()
        self.monitor_item = monitor_item
        self.db_name = db_name
        self.write_time = write_time
        self.share = share

    def run(self):
        put_data(self.monitor_item, self.db_name, self.write_time, self.share)


def cluster_collect_and_write_data(share=None, write_time=None):
    # if this node is master
    time_out = 15

    threads = []
    if write_time is None:
        write_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        for item in cluster_monitor_item.keys():
            monitor_thread = ClusterRecord(item, cluster_monitor_item[item], write_time, share)
            monitor_thread.start()
            threads.append(monitor_thread)


        for thread in threads:
            thread.join(time_out)

            # auto exit after 15s
        """
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(15)
        """
    except Exception, err:
        print err
        sys.exit(1)
        # threads = []
        # del threads[:]
        # for item in cluster_monitor_item.keys():
        #     threads.append(Process(target=put_data, args=[item, cluster_monitor_item[item]]))
        # for t in threads:
        #     t.start()
        # time_waited = 0
        # then = time.time()
        # is_alive = True
        # while is_alive:
        #     for p in threads:
        #         if time_waited >= time_out:
        #             p.terminate()
        #         else:
        #             p.join(time_out - time_waited)
        #         time_waited = time.time() - then
        #     is_alive = False
        #     for p in threads:
        #         if p.is_alive():
        #             is_alive = True
        # # for item in cluster_monitor_item.keys():
        # #     put_data(item, cluster_monitor_item[item])


def query_perf_data(query_perftype, query_period, database_name, if_json=False):
    select_current = "select record_time,device,device_throughput from %s " \
                     "where record_time = (select record_time from %s " \
                     "order by record_time desc limit 1) " \
                     "order by record_time, device;" % (query_perftype, query_perftype)

    select_period = "select record_time,device,device_throughput from %s " \
                    "where record_time > datetime('now', 'localtime', '-%s seconds') " \
                    "order by record_time, device;" % (query_perftype, query_period)

    con = None
    cur = None
    return_list = []
    try:
        con = connect_db(database_name)
        cur = con.cursor()
        query_list = None
        if int(query_period) == 0:
            query_list = cur.execute(select_current)
        else:
            query_list = cur.execute(select_period)
        if query_list:
            return_list = query_list.fetchall()

        if if_json:
            print json.dumps(return_list)
            pass
        else:
            print "Data_name: {0}".format(query_perftype)
            print "{:<30}{:<30}".format("time_stamp", "Data_value")
            for item in return_list:
                print "{:<30}{}: {}".format(item[0], item[1], item[2])

    except Exception, err:
        if "no such table" in str(err):
            _check_table(cur, query_perftype)
            con.commit()
        print >> sys.stdout, err
        sys.exit(1)
    finally:
        if con:
            con.close()


def NFS_Bandwidth(query_period, if_json):
    query_perf_data("NFS_Bandwidth", query_period, "cluster_Nfs_Bandwidth.db", if_json=if_json)


def NFS_Out_Bandwidth(query_period, if_json):
    query_perf_data("NFS_Out_Bandwidth", query_period, "cluster_Nfs_Out_Bandwidth.db", if_json=if_json)


def NFS_In_Bandwidth(query_period, if_json):
    query_perf_data("NFS_In_Bandwidth", query_period, "cluster_Nfs_In_Bandwidth.db", if_json=if_json)


def Connected_NFS_Client_Count(query_period, if_json):
    query_perf_data("Connected_NFS_Client_Count", query_period, "cluster_Nfs_Client_Count.db", if_json=if_json)


def CIFS_Bandwidth(query_period, if_json):
    query_perf_data("CIFS_Bandwidth", query_period, "cluster_Cifs_Bandwidth.db", if_json=if_json)


def CIFS_Out_Bandwidth(query_period, if_json):
    query_perf_data("CIFS_Out_Bandwidth", query_period, "cluster_Cifs_Out_Bandwidth.db", if_json=if_json)


def CIFS_In_Bandwidth(query_period, if_json):
    query_perf_data("CIFS_In_Bandwidth", query_period, "cluster_Cifs_In_Bandwidth.db", if_json=if_json)


def Connected_CIFS_Client_Count(query_period, if_json):
    query_perf_data("Connected_CIFS_Client_Count", query_period, "cluster_Cifs_Client_Count.db", if_json=if_json)


def NFS_node_OPS(query_period, if_json):
    query_perf_data("NFS_node_OPS", query_period, "cluster_Nfs_Client_Ops.db", if_json=if_json)


def NFS_node_Read_OPS(query_period, if_json):
    query_perf_data("NFS_node_Read_OPS", query_period, "cluster_Nfs_Client_Read_Ops.db", if_json=if_json)


def NFS_node_Write_OPS(query_period, if_json):
    query_perf_data("NFS_node_Write_OPS", query_period, "cluster_Nfs_Client_Write_Ops.db", if_json=if_json)

if __name__ == '__main__':
    cluster_monitor_item = {"NFS_Bandwidth": "cluster_Nfs_Bandwidth.db",
                            "NFS_Out_Bandwidth": "cluster_Nfs_Out_Bandwidth.db",
                            "NFS_In_Bandwidth": "cluster_Nfs_In_Bandwidth.db",
                            "Connected_NFS_Client_Count": "cluster_Nfs_Client_Count.db",
                            "CIFS_Bandwidth": "cluster_Cifs_Bandwidth.db",
                            "CIFS_Out_Bandwidth": "cluster_Cifs_Out_Bandwidth.db",
                            "CIFS_In_Bandwidth": "cluster_Cifs_In_Bandwidth.db",
                            "Connected_CIFS_Client_Count": "cluster_Cifs_Client_Count.db",
                            "NFS_node_OPS": "cluster_Nfs_Client_Ops.db",
                            "NFS_node_Read_OPS": "cluster_Nfs_Client_Read_Ops.db",
                            "NFS_node_Write_OPS": "cluster_Nfs_Client_Write_Ops.db"}
							
							
    try:
        parser = OptParser.OptParser()
        parser.append("help", "{-h|--help}")
        parser.append("start", "--start")
        parser.append("record", "--record")
        m_name, m_opts = parser.parse(sys.argv[1:])
    except Exception, e:
        print e
        print "Error(610): Invalid input! "
        sys.exit(1)


    if m_name == "start":
        os.system("/usr/bin/python /usr/bin/cluster_performance_handler.py --record 2>&1 >>/dev/null &")
    elif m_name == "record":
        main()
