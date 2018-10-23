#!/usr/bin/python
#coding:utf-8

import getopt
import os
import commands
import sys
import re
import icfs_util

def ldap_check():
    ip_port_stat,ip_port_out = commands.getstatusoutput("cat /etc/openldap/ldap.conf | grep -v '#' | grep -w 'URI' | awk -F/ '{print $3}'")
    if ip_port_stat != 0:
        print ip_port_out
        sys.exit(1)
    if ip_port_out == '' :
        icfs_util.error('042')
    else:
        ip_port = ip_port_out.split(':')
        if len(ip_port) == 2:
            ip = ip_port[0]
            port = ip_port[1]
        else:
            icfs_util.error('043')

def ldap_query():
    ip = None
    port = None
    ip_port_stat,ip_port_out = commands.getstatusoutput("cat /etc/openldap/ldap.conf | grep -v '#' | grep -w 'URI' | awk -F/ '{print $3}'")
    if ip_port_stat != 0:
        print ip_port_out
        sys.exit(1)
    if ip_port_out == '' :
        icfs_util.error('042')

    ip_port = ip_port_out.split(':')
    if len(ip_port) == 2:
        ip = ip_port[0]
        port = ip_port[1]
    else:
        icfs_util.error('043')
    
    base_dn_stat,base_dn_out = commands.getstatusoutput("cat /etc/openldap/ldap.conf | grep -v '#' | grep -w 'BASE' | awk '{print $2}'")
    if base_dn_stat != 0:
        print base_dn_out
        sys.exit(1)

    if base_dn_out == '':
        baseDN = 'None'
    else:
        baseDN = base_dn_out
    
    print '%-16s%-16s%-16s%s' % ('IP', 'Port', 'LDAP/LDAPS', 'BaseDN')
    print '%-16s%-16s%-16s%s' % (ip, port, 'ldap', baseDN)

def ldap_query_user():
    ip_port_stat,ip_port_out = commands.getstatusoutput("cat /etc/openldap/ldap.conf | grep -v '#' | grep -w 'URI' | awk -F/ '{print $3}'")
    if ip_port_stat != 0:
        print ip_port_out
        sys.exit(1)
    if ip_port_out == '' :
        icfs_util.error('042')

    ip_port = ip_port_out.split(':')
    if len(ip_port) != 2:
        icfs_util.error('043')
    
    base_dn_stat,base_dn_out = commands.getstatusoutput("cat /etc/openldap/ldap.conf | grep -v '#' | grep -w 'BASE' | awk '{print $2}'")
    if base_dn_stat != 0:
        print base_dn_out
        sys.exit(1)

    if base_dn_out == '':
        icfs_util.error('044')
    
    ldap_user_stat,ldap_user_out = commands.getstatusoutput("ldapsearch -o nettimeout=5 -LLL -x 'objectClass=posixAccount' uid")
    if ldap_user_stat != 0:
        print ldap_user_out
        sys.exit(1)
    
    print "Username"
    ldap_user = re.findall("uid:\s*(.*?)(?:\n|$)", ldap_user_out)
    for i in ldap_user:
        print i

def ldap_query_group():
    ip_port_stat,ip_port_out = commands.getstatusoutput("cat /etc/openldap/ldap.conf | grep -v '#' | grep -w 'URI' | awk -F/ '{print $3}'")
    if ip_port_stat != 0:
        print ip_port_out
        sys.exit(1)
    if ip_port_out == '' :
        icfs_util.error('042')

    ip_port = ip_port_out.split(':')
    if len(ip_port) != 2:
        icfs_util.error('043')
    
    base_dn_stat,base_dn_out = commands.getstatusoutput("cat /etc/openldap/ldap.conf | grep -v '#' | grep -w 'BASE' | awk '{print $2}'")
    if base_dn_stat != 0:
        print base_dn_out
        sys.exit(1)

    if base_dn_out == '':
        icfs_util.error('044')
    
    ldap_group_stat,ldap_group_out = commands.getstatusoutput("ldapsearch -o nettimeout=5 -LLL -x 'objectClass=posixGroup' cn")
    if ldap_group_stat != 0:
        print ldap_group_out
        sys.exit(1)
    
    print "Groupname"
    ldap_group = re.findall("cn:\s*(.*?)(?:\n|$)", ldap_group_out)
    for i in ldap_group:
        print i

def query():
    try: 
        opts,argv = getopt.getopt(sys.argv[1:], "ug", ['ldap','query'])
    except getopt.GetoptError,err:
        icfs_util.error('002')
    
    if argv != []:
        icfs_util.error('002')
    
    if len(sys.argv) == 3 and sys.argv[1] == "--ldap" and sys.argv[2] == "--query":
        ldap_query()
    elif len(sys.argv) == 4 and sys.argv[1] == "--ldap" and sys.argv[2] == "--query" and sys.argv[3] == "-u":
        ldap_query_user()
    elif len(sys.argv) == 4 and sys.argv[1] == "--ldap" and sys.argv[2] == "--query" and sys.argv[3] == "-g":
        ldap_query_group()
    else:
        icfs_util.error('002')
