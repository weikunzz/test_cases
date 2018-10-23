#!/usr/bin/python
#coding:utf-8

import getopt
import sys
import icfs_util
import commands

def nis_check():
    # yptest
    test_out = commands.getoutput("yptest")
    if 'domainname is not set' in test_out :
        icfs_util.error('017')
    elif  'Can\'t communicate with ypbind' in test_out:
        icfs_util.error('001')
    
    # check ypbind status
    ypbind_stat,ypbind_out = commands.getstatusoutput('service ypbind status')
    if "ypbind is stopped" in ypbind_out:
        ypbind_stat_1,ypbind_out_1 = commands.getstatusoutput('service ypbind start')
        if ypbind_stat_1 != 0:
            icfs_util.error('029')
    elif "unrecognized service" in ypbind_out:
        icfs_util.error('030')
    
    # check ypbind config
    nis_stat,nis_out = commands.getstatusoutput("cat /etc/yp.conf | grep domain | grep -v '#'|awk '{print $2,$4}'")
    if nis_stat != 0 or nis_out == '':
        icfs_util.error('018')

def nis_query():
    # nis_check()
    status,output = commands.getstatusoutput("cat /etc/yp.conf | grep domain | grep -v '#'|awk '{print $2,$4}'")
    if status != 0 or output == '':
        icfs_util.error('018')
    else:
        domain_ip = output.split()
    
    print '%-32s%s'%('Domain', 'Ip')
    print '%-32s%s'%(domain_ip[0], domain_ip[1])

def nis_query_user():
    nis_check()
    status,output = commands.getstatusoutput("ypcat passwd | awk -F: '{print $1}'")
    if status != 0 or 'No such' in output or 'Reason:' in output:
        print output
        sys.exit(1)
    
    print "Username"
    nis_user = output.split('\n')
    for i in nis_user:
        print i

def nis_query_group():
    nis_check()
    status,output = commands.getstatusoutput("ypcat group | awk -F: '{print $1}'")
    if status != 0 or 'No such' in output or 'Reason:' in output:
        print output
        sys.exit(1)
    
    print "Groupname"
    nis_group = output.split('\n')
    for i in nis_group:
        print i

def query():
    try: 
        opts,argv = getopt.getopt(sys.argv[1:], "ug", ['nis','query'])
    except getopt.GetoptError,err:
        icfs_util.error('002')
    
    if argv != []:
        icfs_util.error('002')
    
    if len(sys.argv) == 3 and sys.argv[1] == "--nis" and sys.argv[2] == "--query":
        nis_query()
    elif len(sys.argv) == 4 and sys.argv[1] == "--nis" and sys.argv[2] == "--query" and sys.argv[3] == "-u":
        nis_query_user()
    elif len(sys.argv) == 4 and sys.argv[1] == "--nis" and sys.argv[2] == "--query" and sys.argv[3] == "-g":
        nis_query_group()
    else:
        icfs_util.error('002')
