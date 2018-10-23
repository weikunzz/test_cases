#!/usr/bin/python
#coding:utf-8
# -*- copyright -*-
import sys
import icfs_util
import commands
import getopt

def test():
    
    domain_name = None
    try:
        opts,argv = getopt.getopt(sys.argv[1:],(''),['ad','test','domain='])
    except getopt.GetoptError,err:
        icfs_util.error('002')
    if argv != []:
        icfs_util.error('002')
    if len(opts) != 3:
        icfs_util.error('002')
    else:
        for o,a in opts:
            if o in '--domain':
                domain_name = a
            
        if domain_name == None :
            icfs_util.error('002')
        else :
            icfs_util.domain_format(domain_name)
            test_stat,test_out = commands.getstatusoutput(' ping -c 1 %s '%domain_name)
            if test_stat != 0:
                print test_out,'\n',icfs_util.error('014')
                sys.exit(1)
            else:
                print 'test succeed !!!'