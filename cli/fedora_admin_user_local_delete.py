#!/usr/bin/python
# coding:utf-8
# -*- copyright -*-

# change log list
# 20170209 shaoning (all_funtion) statement to judge whether user exists changed

import sys
import platform
import getopt
import commands
import icfs_util
import psutil


def kill_user_process(username):
    pid_list = psutil.pids()
    for pid in pid_list:
        try:
            p = psutil.Process(pid)
        except psutil.NoSuchProcess:
            continue
        if p.username() == username:
            p.terminate()
        else:
            continue


def synchronize_file(file_name):
    ret_dict = icfs_util.run_remote_copy("*", file_name, file_name)
    fail_list = [name for name, ret in ret_dict.items() if ret["retcode"] != 0]
    if fail_list:
        print "Error(1399): Unknown error", "synchronize %s to %s" % (file_name, ",".join(fail_list))
        sys.exit(1)


def user_delete(user_name):
    icfs_util.user_name_format(user_name)
    # does the username exit?  "." matchs any character, so need to be escaped
    user_a, user_b = commands.getstatusoutput("cat /etc/passwd | grep '^%s:'" % user_name.replace(".", r"\."))
    if user_a != 0:
        icfs_util.error('007', platform.node())  # user not exit

    uid = user_b.split(':')[2]
    if int(uid) < icfs_util.get_min_uid():
        icfs_util.error('010')

    # 删除smb用户
    commands.getstatusoutput("smbpasswd -x %s" % user_name)
    kill_user_process(user_name)
    # userdel -f 强制删除用户，即使已登录
    status, output = commands.getstatusoutput("userdel %s" % user_name)
    if status != 0:
        print output
        sys.exit(1)

    # pack all files
    file_list = ["/etc/passwd", "/etc/group", "/etc/shadow"]
    status, output = commands.getstatusoutput("tar czvf /etc/.local_user.tar.gz %s" %
                                              " ".join(file_list))
    if status != 0:
        print "Error(1399): Unknown error", output
        sys.exit(1)

    # synchonize files
    synchronize_file("/etc/.local_user.tar.gz")
    icfs_util.run_remote_cmd("*", "tar xvf /etc/.local_user.tar.gz -C /;rm -f /etc/.local_user.tar.gz")
    icfs_util.run_remote_cmd("*", "smbpasswd -x %s" % user_name)


def group_delete(group_name):
    icfs_util.group_name_format(group_name)
    # is the groupname exit?  "." matchs any character, so need to be escaped
    group_a, group_b = commands.getstatusoutput("cat /etc/group | grep '^%s:'" % group_name.replace(".", r"\."))
    if group_a != 0:
        icfs_util.error('008', platform.node())  # group not exit

    gid = group_b.split(':')[2]
    if int(gid) <= icfs_util.get_min_uid() or group_name == 'default_group':
        icfs_util.error('009')

    delgroup_stat, delgroup_out = commands.getstatusoutput('groupdel %s ' % group_name)
    if delgroup_stat != 0:
        if 'cannot remove the primary' in delgroup_out:
            icfs_util.error('019', '')
        else:
            print delgroup_out
            sys.exit(1)

    synchronize_file("/etc/group")


def delete():
    opts = None
    argv = None

    # check current user
    if icfs_util.current_user != 'root':
        icfs_util.error('012')

    # check salt status
    icfs_util.salt_run()

    try:
        opts, argv = getopt.getopt(sys.argv[1:], 'u:g:', ['local', 'delete'])
    except getopt.GetoptError:
        icfs_util.error('002')

    if argv:
        icfs_util.error('002')

    if len(opts) != 3:
        icfs_util.error('002')

    for k, v in opts:
        if k == "-u":
            username = v
            user_delete(username)
        elif k == '-g':
            groupname = v
            group_delete(groupname)
