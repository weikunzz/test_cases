#!/usr/bin/python
#coding:utf-8
# -*- copyright -*-

import sys
import commands
import getopt
import icfs_util

def test():
    
    server_ip = None

    try:
        opts,argv = getopt.getopt(sys.argv[1:],(''),['ldap','test','ip='])
    except getopt.GetoptError,err:
        icfs_util.error('002')
    if argv != []:
        icfs_util.error('002')
    if len(opts) != 3:
        icfs_util.error('002')
    else:
        for o,a in opts:
            if o in '--ip':
                
                server_ip = a
            
        if server_ip == None :
            icfs_util.error('002')
        else :
            icfs_util.ip_format(server_ip)
            test_stat,test_out = commands.getstatusoutput(' ping -c 1 %s '%server_ip)
            if test_stat != 0:
                print test_out,'\n',icfs_util.error('014')
                sys.exit(1)
            else:
                print 'test succeed !!!'
                        
                
            
            
            
            
            
            
            