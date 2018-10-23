#!/usr/bin/python
# coding:utf-8

import getopt
import os
import sys
import commands
import icfs_util

def quit_ldap():
    argv = None
    opts = None
    try:
        opts,argv = getopt.getopt(sys.argv[1:], '', ['ldap', 'quit'])
    except getopt.GetoptError,err:
        icfs_util.error('002')
    
    if argv != [] or len(opts) != 2:
        icfs_util.error('002')

    task = commands.getoutput("icfs-admin-task --query")
    if "ldap_quit" in task:
        icfs_util.error('3006')
    
    os.system("python /usr/bin/task-manage ldap_quit > /dev/null & ")
