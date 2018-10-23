#!/usr/bin/python
# coding:utf-8
# -*- copyright -*-

# change log list
# 20161214 shaoning (changegroup) handle index error
# 20170209 shaoning (all_funtion) statement to judge whether user exists changed
# 20170214 shaoning (change_password) password support more special characters

import sys
import platform
import getopt
import commands
import icfs_util
import re


def synchronize_file(file_name):
    status, output = commands.getstatusoutput("salt-cp '*' cmd.run %s %s" % (file_name, file_name))
    if status != 0 or "false" in output:
        print output
        sys.exit(1)


def passwd_format(passwd):
    if len(passwd) < 8 or len(passwd) > 32:
        icfs_util.error('023')
    elif re.findall(r'[^\w@%?_,.]', passwd):
            icfs_util.error('002')


def change_password(user_name, password):
    # support special characters
    escaped_password = ""
    for i in password:
        escaped_password += "\\" + i
    commands.getoutput("echo %s|passwd --stdin %s" % (escaped_password, user_name))
    synchronize_file("/etc/shadow")
    # 修改smb用户密码
    icfs_util.run_remote_cmd("*", "(echo %s;echo %s )| smbpasswd -s -a %s" % (escaped_password, escaped_password, user_name))


def change_group(user_name, group_name):
    status, output = commands.getstatusoutput("grep '^%s:' /etc/group" % group_name.replace(".", r"\."))
    if status != 0:
        # group not exist
        icfs_util.error('008', platform.node())

    gid = output.split(':')[2]
    if int(gid) < icfs_util.get_min_uid():
        icfs_util.error('020')
    status, output = commands.getstatusoutput("usermod -g %s %s" % (group_name, user_name))
    if status != 0:
        print output
        sys.exit(1)
    synchronize_file("/etc/passwd")


def set():
    opts = None
    argv = None
    username = None
    password = None
    group = None
    if icfs_util.current_user != 'root':
        icfs_util.error('012')
    try:
        opts, argv = getopt.getopt(sys.argv[1:], 'u:g:', ['passwd=', 'local', 'set'])
    except getopt.GetoptError:
        icfs_util.error('002')
        
    if len(opts) > 5 or len(opts) < 4:
        icfs_util.error('002')
    if argv:
        icfs_util.error('002')

    for o, a in opts:
        if o in '-u':
            if username is not None:
                icfs_util.error('002')
            username = a
        elif o in '--passwd':
            if password is not None:
                icfs_util.error('002')
            password = a
        elif o in '-g':
            if group is not None:
                icfs_util.error('002')
            group = a
    icfs_util.user_name_format(username)
    icfs_util.salt_run()
    if username is None:
        icfs_util.error('011')

    if password is None and group is None:
        icfs_util.error('002')

    status, output = commands.getstatusoutput("grep '^%s:' /etc/passwd" % username.replace(".", r"\."))
    if status != 0:
        # user not exit
        icfs_util.error('007', platform.node())

    uid = output.split(':')[2]
    if int(uid) < icfs_util.get_min_uid():
        icfs_util.error('013')

    if password is not None:
        passwd_format(password)
        change_password(username, password)
    if group is not None:
        icfs_util.group_name_format(group)
        change_group(username, group)
