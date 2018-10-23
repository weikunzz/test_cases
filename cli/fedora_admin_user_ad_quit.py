#!/usr/bin/python
# coding:utf-8
# -*- copyright -*-

# change log list
# 20170214 shaoning (quit) password support more special characters

import sys
import os
import icfs_util
import commands
import getopt

quit_stat = None
quit_out = None


def quit():
    domain = None
    admin = None
    password = None
    global quit_out
    global quit_stat
    cluster = False
    
    try:
        opts, argv = getopt.getopt(sys.argv[1:], 'u:', ['ad', 'quit', 'passwd=', 'cluster'])
    except getopt.GetoptError, err:
        icfs_util.error('002')
    if argv != []:
        icfs_util.error('002')
    # if len(sys.argv[1:]) != 6:
    #     icfs_util.error('002')

    for o, a in opts:
        if o in '-u':
            admin = a
        elif o in '--passwd':
            password = a
        elif o in '--cluster':
            cluster = True
    icfs_util.passwd_format(password)
    icfs_util.salt_run()
    # mon_stat,mon_out = commands.getstatusoutput("cat /etc/icfs/icfs.conf |grep mon_host |awk ' {print $3}'")
    # mon_list = mon_out.split(',')
    
    # for mon in mon_list:

    task = commands.getoutput("icfs-admin-task --query")
    if "ad_quit" in task:
        icfs_util.error('3006')

    # os.system("python /usr/bin/task-manage %s %s %s "%('ad_quit',admin+'%',password))
    # support special characters
    escaped_password = ""
    for i in password:
        escaped_password += "\\" + i
    if cluster:
        os.system("python /usr/bin/task-manage %s %s %s > /dev/null &" % ('ad_quit_cluster', admin+'%', escaped_password))
    else:
        os.system("python /usr/bin/task-manage %s %s %s > /dev/null &" % ('ad_quit', admin+'%', escaped_password))
    
    # quit_stat,quit_out = commands.getstatusoutput("salt  '*' cmd.run 'net ads leave -U %s%s;echo $?'"%(admin+'%',password))
    # winb_stat,winb_out = commands.getstatusoutput("salt '*' cmd.run 'service winbind restart'")
    # if quit_stat != 0  or quit_out.split('\n')[-1].strip() != '0' or 'are we joined' in quit_out :
    #     #print quit_out
    #     icfs_util.error('005','')
    # else:
    #     print 'quit succeed at %s !!!'%mon
