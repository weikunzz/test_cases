# -*- coding: utf-8 -*-

# from icfs_util import IcfsVersion


# return value: True-use salt, False-use ansible
def use_salt():
    return True
    # use salt before version 3.6.1.1
    # if IcfsVersion.current_version() < IcfsVersion("3.6.1.1"):
    #     return False
    # else:
    #     return True


# return value example: ['host1', 'host2', 'host3']
def get_host_list():
    if use_salt():
        import SaltRunner
        return SaltRunner.list_hosts()
    else:
        import AnsibleRunner
        return AnsibleRunner.list_hosts()


# tgt:  '*' stands all hosts, 'node1,node2,node3' stands a list of hosts
# return value: { node_name1: {'status': status}, node_name2: 'status': status}, ... }
#      such as: { 'node1': {'status': True},
#                 'node2': {'status': False},
#                 'node3': {'status': True} }
#       status: True-reachable False-not reachable
def run_ping(tgt):
    if use_salt():
        import SaltRunner
        return SaltRunner.run_ping(tgt)
    else:
        import AnsibleRunner
        return AnsibleRunner.run_ping(tgt)


# tgt:  '*' stands all hosts, 'node1,node2,node3' stands a list of hosts
# cmd:  commnad to run
# return value: { node_name1: {'retcode': retcode, 'stdout': stdout, 'stderr': stderr}, ... }
#      such as: { 'node1': {'retcode': 0, 'stdout': 'abc', 'stderr': ''},
#                 'node2', {'retcode': 1, 'stdout': '', 'stderr': 'error'},
#                 'node3', {'retcode': -1, 'stdout': '', 'stderr': 'no return'} }
#      retcode: 0:success 1:failed -1:not accessable
def run_cmd(tgt, cmd):
    if use_salt():
        import SaltRunner
        return SaltRunner.run_cmd(tgt, cmd)
    else:
        import AnsibleRunner
        return AnsibleRunner.run_shell(tgt, cmd)


# tgt:  '*' stands all hosts, 'node1,node2,node3' stands a list of hosts
# src:  source file path
# dest: destination file path
# return value: { node_name1: {'retcode': retcode, 'retout': retout}, ... }
#      such as: { 'node1': {'retcode': 0, 'retout': ''},
#                 'node2', {'retcode': 1, 'retout': 'error'},
#                 'node3', {'retcode': -1, 'retout': 'no return'} }
#      retcode: 0:success 1:failed -1:not accessable
def run_copy(tgt, src, dest):
    if use_salt():
        import SaltRunner
        return SaltRunner.run_copy(tgt, src, dest)
    else:
        import AnsibleRunner
        return AnsibleRunner.run_copy(tgt, src, dest)


# tgt:  '*' stands all hosts, 'node1,node2,node3' stands a list of hosts
# src:  source file path
# dest: destination file path
# return value: True-success  False-failed
def run_copy_with_rollback(tgt, src, dest):
    if src == dest:
        raise ValueError("In case of rollback error, source file can not be same with destination file")

    ret_list = run_copy(tgt, src, src)
    success_list = [node_name for node_name, status, output in ret_list if status == 0]
    if len(success_list) == len(ret_list):
        # success on all nodes
        run_cmd(tgt, "mv -f %s %s" % (src, dest))
        return True
    else:
        # failed in same nodes, try rollback
        if success_list:
            run_cmd(",".join(success_list), "rm -f %s" % src)
        return False
