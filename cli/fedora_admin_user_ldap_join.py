#!/usr/bin/python
#coding:utf-8

import getopt
import os
import re
import sys
import commands
import icfs_util

def join():
    port = None
    serverIP = None
    protocol = None
    base_dn = None
    try:
        opts,argv = getopt.getopt(sys.argv[1:],('b:'),['ldap','join','ip=','port='])
    except getopt.GetoptError,err:
        icfs_util.error('002')
    
    if argv != [] or len(opts) !=5:
        icfs_util.error('002')
    
    for o,a in opts:
        if  o  in '-b':
            base_dn = a 
        elif o in '--ip':
            serverIP = a
        elif o in '--port':
            port = a
    
    if base_dn == None or serverIP == None or  port == None :
        icfs_util.error('002')
    
    icfs_util.ip_format(serverIP)
    icfs_util.port_format(port)
    icfs_util.dn_format(base_dn)
    icfs_util.ping_all(serverIP)
    task = commands.getoutput("icfs-admin-task --query")
    if "ldap_join" in task:
        icfs_util.error('3006')
    
    os.system("python /usr/bin/task-manage %s %s %s %s > /dev/null & "%('ldap_join',base_dn,serverIP,port))
