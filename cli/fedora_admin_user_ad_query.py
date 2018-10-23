#!/usr/bin/python
#coding:utf-8
# -*- copyright -*-

import sys
import re
import icfs_util
import getopt
import commands

#user_arr1 = commands.getoutput('wbinfo -u') 
join_stat = 'ok'
def query():
    #test_domain_name = commands.getoutput("cat /etc/krb5.conf | grep -w 'default_realm'| awk '{print $3}'").lower()
    #dns_test_st,dns_test_out  = commands.getstatusoutput('ping -c 2 %s'%test_domain_name )
    #if dns_test_st != 0:
    #    icfs_util.error('006',test_domain_name)
    user_arr1 = commands.getoutput('wbinfo -u') 
    global join_stat
    try:
        opts,argv = getopt.getopt(sys.argv[1:],('ug'),['ad','query'])
    except getopt.GetoptError,err:
        icfs_util.error('002')
    if  len(opts) > 3 or  argv != []:
        icfs_util.error('002')
    else: 
        #condition = commands.getoutput('net ads testjoin')
        if 'could not obtain winbind domain name' in user_arr1 or \
            'command not found'  in user_arr1 or 'Error looking up domain users' in user_arr1:
            join_stat = 'faild'
        # if 'Clock skew too great' in condition:
            # icfs_util.error('041')
        #elif 'is OK' in condition :
        if '-u' not in sys.argv[1:] and  '-g' not in sys.argv[1:]:
            if  len(opts) != 2:
                icfs_util.error('002')
            query_domain_info()
        else:
            for k,v in opts:
                if k in '-u' :
                    query_user()
                elif  k in '-g' :
                    query_group()
        
            
def query_user():
    user_arr1 = commands.getoutput('wbinfo -u') 
    domain_user = []
    print 'Username'
    for user in user_arr1.split():
        if '\\' not in user:
            domain_user.append(user)
    if domain_user == [] or join_stat == 'faild':
        print 'None'
    else :
        for user1 in domain_user:
            print  user1
    
def query_group():
    group_arr1 = commands.getoutput('wbinfo -g') 
    print 'Groupname'
    if group_arr1 == '' or join_stat == 'faild':
        print 'None'
    else:
        for group in group_arr1.split('\n'):
            print  group

def query_domain_info():
    print '%-16s \t %-16s \t %-16s \t %-16s \t %-16s \t %s' % ('Administrator', 'Domain', 'IP', 'Condition', "SecondDomain", "NetbiosName")
    if join_stat == 'faild':
        print '%-16s \t %-16s \t %-16s \t %-16s \t %-16s \t %s' % ('None', 'None', 'None', 'quit', "None", "None")
        sys.exit(0)

    full_domain_name = commands.getoutput("cat /etc/krb5.conf | grep -w 'default_realm'| awk '{print $3}'").lower()
    # second_domain_name
    domain_name_info = commands.getoutput("cat /etc/krb5.conf | sed -n '/\[domain_realm\]/,/\[appdefaults\]/{//!p}'")
    domain_name_list = domain_name_info.split("\n")
    domain_name_list.remove("")
    if len(domain_name_list) < 4:
        second_domain_name = "None"
    else:
        second_domain_name = domain_name_list[3].split("=")[-1]
        second_domain_name = second_domain_name.strip().lower()
    server_ip1 = commands.getoutput("cat /etc/krb5.conf | grep -w 'admin_server'")
    server_ip = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',server_ip1)
    admin_list = commands.getoutput("wbinfo --group-info 'domain admins'").split(':')[-1].split(',')
    if admin_list == [] or 'WBC_ERR_DOMAIN_NOT_FOUND' in admin_list[0] or 'Could not get info for group domain admins' in admin_list[0]:
        print '%-16s \t %-16s \t %-16s \t %-16s \t %-16s \t %s' % ('None', 'None', 'None', 'quit', "None", "None")
        sys.exit(0)

    # get netbios name
    netbios_name = "None"
    smb_conf_parser = icfs_util.NewConfigParser()
    smb_conf_parser.read("/etc/samba/smb.conf")
    if smb_conf_parser.has_option("global", "netbios name"):
        netbios_name = smb_conf_parser.get("global", "netbios name")

    i = 1
    if admin_list == ['']:
        admin_list = ['administrator']
    for admin in admin_list:
        if i == 1:
            print '%-16s \t %-16s \t %-16s \t %-16s \t %-16s \t %s' % (admin, full_domain_name, server_ip[0], 'join', second_domain_name, netbios_name)
            i = 2
        else:
            print '%-16s \t %-16s \t %-16s \t %-16s \t %-16s \t %s' % (admin, '', '', '', '', '')
