#!/usr/bin/python
#coding:utf-8

import getopt
import os
import sys
import commands
import icfs_util

def join():
    ip = None
    domain = None
    domain_name = None
    
    try:
        opts,argv = getopt.getopt(sys.argv[1:],(),[ 'nis','join','ip=','domain='])
    except getopt.GetoptError,err:
        icfs_util.error('002')
    
    if argv != [] or len(opts) != 4:
        icfs_util.error('002')
    
    num_ip=0
    num_domain=0
    for  o,a in opts:
        if o in  '--ip':
            num_ip+=1
            if num_ip>1:
                icfs_util.error('002')
            ip = a
        if o in '--domain':
            num_domain+=1
            if num_domain>1:
                icfs_util.error('002')
            domain = a
    
    if domain == None or ip == None:
        print 'None'
        icfs_util.error('002')
    
    icfs_util.domain_format(domain)
    icfs_util.ip_format(ip)
    icfs_util.ping_all(ip)
    task = commands.getoutput("icfs-admin-task --query")
    if "nis_join" in task:
        icfs_util.error('3006')
    
    os.system("python /usr/bin/task-manage %s %s %s > /dev/null &"%('nis_join',domain,ip))
