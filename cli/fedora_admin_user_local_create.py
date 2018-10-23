#!/usr/bin/python
# coding:utf-8
# -*- copyright -*-

# change log list
# 20161214 shaoning (changegroup) handle index error
# 20170209 shaoning (all_funtion) statement to judge whether user exists changed
# 20170214 shaoning (user_create) password support more special characters

import sys
import getopt
import commands
import icfs_util
import re


def synchronize_file(file_name):
    ret_dict = icfs_util.run_remote_copy("*", file_name, file_name)
    fail_list = [name for name, ret in ret_dict.items() if ret["retcode"] != 0]
    if fail_list:
        print "Error(1399): Unknown error", "synchronize %s to %s" % (file_name, ",".join(fail_list))
        sys.exit(1)


def passwd_format(passwd):
    if len(passwd) < 8 or len(passwd) > 32:
        icfs_util.error('023')
    elif re.findall(r'[^\w@%?_,.]', passwd):
            icfs_util.error('002')


def group_create(group_name):
    status, output = commands.getstatusoutput("wbinfo -g |grep -v '\\\\'|grep -x %s" % group_name.replace(".", r"\."))
    if status == 0:
        icfs_util.error('016')
    status, output = commands.getstatusoutput("cat /etc/group | awk -F: '{print $1}' | grep -x '%s'"
                                              % group_name.replace(".", r"\."))
    if status == 0:
        icfs_util.error('004')
    status, output = commands.getstatusoutput("groupadd %s" % group_name)
    if status != 0:
        print output
        sys.exit(1)

    synchronize_file("/etc/group")


def user_create():
    opts = None
    argv = None
    username = None
    password = None
    groupname = None

    if icfs_util.current_user != 'root':
        icfs_util.error('012')
    icfs_util.salt_run()
    try:
        opts, argv = getopt.getopt(sys.argv[1:], 'u:g:', ['passwd=', 'local', 'create'])
    except getopt.GetoptError:
        icfs_util.error('002')
    if argv != [] or len(opts) > 5:
        icfs_util.error('002')
    # choose create user or create group?
    if ('-g' in sys.argv) and ('-u' not in sys.argv and '--passwd' not in sys.argv):  # create group
        if len(opts) > 3:
            icfs_util.error('002')
        for k, v in opts:
            if k in "-g":
                groupname = v
        icfs_util.group_name_format(groupname)
        group_create(groupname)
    else:
        if '-u' in sys.argv:
            num = sys.argv.index('-u')
            # -u must has a argument
            if num == len(sys.argv)-1:
                icfs_util.error('002')
        else:
            icfs_util.error('002')

        if '--passwd' in sys.argv:
            num = sys.argv.index('--passwd')
            if num == len(sys.argv)-1:
                icfs_util.error('002')
        else:
            icfs_util.error('002')
        
        if '-g' in sys.argv:
            num = sys.argv.index('-g')
            if num == len(sys.argv)-1:
                icfs_util.error('002')

        for k, v in opts:
            if k in "-u":
                if username is not None:
                    icfs_util.error('002')
                username = v
            elif k in '--passwd':
                if password is not None:
                    icfs_util.error('002')
                password = v
            elif k in "-g":
                groupname = v
        if username is None or password is None:
            icfs_util.error('002')
        icfs_util.user_name_format(username)
        passwd_format(password)
        # is the user exist at ad domain
        status, output = commands.getstatusoutput("wbinfo -u |grep -v '\\\\'|grep -x %s" % username.replace(".", r"\."))
        if status == 0:
            icfs_util.error('015')
        # is the username exist? if it exists return 0,else return others
        status, output = commands.getstatusoutput("cat /etc/passwd | awk -F: '{print $1}' | grep -x '%s'"
                                                  % username.replace(".", r"\."))
        if status == 0:
            icfs_util.error('003')
        if groupname is None:
            groupname = 'default_group'
        else:
            icfs_util.group_name_format(groupname)
            status, output = commands.getstatusoutput("cat /etc/group |grep '^%s:'|awk -F: '{print $3}'"
                                                      % groupname.replace(".", r"\."))
            if output != '' and int(output) < icfs_util.get_min_uid():
                icfs_util.error('020')
            commands.getstatusoutput("groupadd %s" % groupname)
        status, output = commands.getstatusoutput("useradd %s -g %s" % (username, groupname))
        if status != 0:
            print output
            sys.exit(1)
        # change password for user
        # support special characters
        escaped_password = ""
        for i in password:
            escaped_password += "\\" + i
        change_a, chang_b = commands.getstatusoutput("echo %s|passwd --stdin %s" % (escaped_password, username))
        if change_a != 0:
            print chang_b
            sys.exit(1)
        # 修改smb用户密码
        smb_a, smb_b = commands.getstatusoutput("(echo %s;echo %s )| smbpasswd -s -a %s"
                                                % (escaped_password, escaped_password, username))
        if smb_a != 0:
            print smb_b
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
        icfs_util.run_remote_cmd("*", "(echo %s;echo %s )| smbpasswd -s -a %s"
                                 % (escaped_password, escaped_password, username))
