#!/usr/bin/python
# coding:utf-8
# -*- copyright -*-

# change log list
# 20170214 shaoning (join) password support more special characters

import os
import sys
import getopt
import commands
import icfs_util
import re


# def copy_back():
#   commands.getoutput('\cp /etc/krb5.conf.copy /etc/krb5.conf')
#   commands.getoutput('\cp /etc/samba/smb.conf.copy /etc/samba/smb.conf')
#   commands.getoutput("salt-cp '*' /etc/krb5.conf /etc/krb5.conf")
#   commands.getoutput("salt-cp '*' /etc/samba/smb.conf")
#   commands.getoutput('rm -f /etc/krb5.conf.copy')
#   commands.getoutput('rm -f /etc/samba/smb.conf.copy')

def netbios_name_format(netbios_name):
    if len(netbios_name) > 32:
        print "Error(050):The netbios name must be between 1 and 32 characters"

    if re.match(r"^[a-zA-Z0-9_-]{1,32}$", netbios_name) is None:
        print "Error(051):Invalid netbios name %s" % netbios_name


def join():
    username = None
    password = None
    domain = None
    second_domain = None
    dcip = None
    netbios_name = None
    cluster = False
    
    try:
        opts, argv = getopt.getopt(sys.argv[1:], 'u:', ['ad', 'join', 'ip=', 'passwd=', 'domain=',
                                                        'second_domain=', 'cluster', 'netbios_name='])
    except getopt.GetoptError, err:
        icfs_util.error('002')
    if argv != []:
        icfs_util.error('002')
    # if len(opts) != 6:
    #     icfs_util.error('002')

    for o, a in opts:
        if o in '-u':
            username = a
        elif o in '--passwd':
            password = a
        elif o in '--domain':
            domain = a
        elif o in '--ip':
            dcip = a
        elif o in '--second_domain':
            second_domain = a
        elif o in "--cluster":
            cluster = True
        elif o in '--netbios_name':
            netbios_name = a
                
    if dcip is None or username is None or password is None or domain is None:
        icfs_util.error('002')

    # cluster must coexist with netbios_name
    if (cluster and netbios_name is None) or (not cluster and netbios_name is not None):
        icfs_util.error('002')

    icfs_util.user_name_format(username)
    icfs_util.domain_format(domain)
    icfs_util.passwd_format(password)
    icfs_util.ip_format(dcip)
    icfs_util.ping_all(dcip)

    if second_domain is not None:
        icfs_util.domain_format(second_domain)
        if domain == second_domain:
            print "Error(610):Invalid input!", "the second domain name can not be same with the domain name"
            sys.exit(1)
    else:
        second_domain = ""

    if netbios_name is not None:
        netbios_name_format(netbios_name)
        # netbios name can't be the same with domain name
        if netbios_name == domain.split(".")[0] or netbios_name == second_domain.split(".")[0]:
            print "Error(058): The netbios name conflicts with domain name"
            sys.exit(1)

    dcip_out = commands.getoutput("cat /etc/resolv.conf|grep -v '#'|grep %s" % dcip)
    if dcip_out == '':
        icfs_util.error('3004')
    task = commands.getoutput("icfs-admin-task --query")
    if "ad_join" in task:
        icfs_util.error('3006')

    # support special characters
    escaped_password = ""
    for i in password:
        escaped_password += "\\" + i

    if cluster:
        os.system("python /usr/bin/task-manage %s %s %s %s %s '%s' %s > /dev/null &"
                  % ('ad_join_cluster', username, escaped_password, domain, dcip, second_domain, netbios_name))
    else:
        os.system("python /usr/bin/task-manage %s %s %s %s %s '%s' > /dev/null &"
                  % ('ad_join', username, escaped_password, domain, dcip, second_domain))

#       dcip_out = commands.getoutput("cat /etc/resolv.conf|grep -v '#'|grep %s"%dcip)
#       if dcip_out == '':
#           print 'please set DNS in /etc/resolv.conf'
#           sys.exit(1)
#       commands.getoutput('\cp /etc/krb5.conf /etc/krb5.conf.copy')
#       commands.getoutput('\cp /etc/samba/smb.conf /etc/samba/smb.conf.copy')
#       krb5 = '''
# [logging]
# default = FILE:/var/log/krb5libs.log
# kdc = FILE:/var/log/krb5kdc.log
# admin_server = FILE:/var/log/kadmind.log

# [libdefaults]
# default_realm = %s
# dns_lookup_realm = true
# dns_lookup_kdc = true
# ticket_lifetime = 24h
# forwardable = yes

# [realms]
# EXAMPLE.COM = {
# kdc = kerberos.example.com:88
# admin_server = kerberos.example.com:749
# default_domain = example.com
# }

# %s = {
# kdc = %s:88
# admin_server = %s:749
# kdc = %s
# }

# TESTINSPUR.COM = {
# kdc = 12.0.11.64
# }

# [domain_realm]
# .example.com = EXAMPLE.COM
# example.com = EXAMPLE.COM

# %s = %s
# .%s = %s
# [appdefaults]
# pam = {
# debug = false
# ticket_lifetime = 36000
# renew_lifetime = 36000
# forwardable = true
# krb4_convert = false
# }
#       '''%(domain.upper(),domain.upper(),dcip,dcip,dcip,domain,domain.upper(),domain,domain.upper())
#       f_krb5=open('/etc/krb5.conf','w')
#       f_krb5.write(krb5)
#       f_krb5.close()
#       cp_krb5_stat,cp_krb5_out=commands.getstatusoutput\
#       ("salt-cp '*' /etc/krb5.conf /etc/krb5.conf")
#       krb5_out=cp_krb5_out.split('\n')
#       for check_krb5 in krb5_out:
#           if not check_krb5.find("True")>=0:
#               icfs_util.error('033','/etc/krb5.conf')
                
#       nsswitch_passwd = commands.getoutput("cat /etc/nsswitch.conf | grep -v '#' | grep -w 'passwd:'")
#       nsswitch_shadow = commands.getoutput("cat /etc/nsswitch.conf | grep -v '#' | grep -w 'shadow:'")
#       nsswitch_group = commands.getoutput("cat /etc/nsswitch.conf | grep -v '#' | grep -w 'group:'")
#       commands.getoutput("sed -i 's/%s/%s/' /etc/nsswitch.conf"%(nsswitch_passwd,'passwd: files winbind'))
#       commands.getoutput("sed -i 's/%s/%s/' /etc/nsswitch.conf"%(nsswitch_shadow,'shadow: files winbind'))
#       commands.getoutput("sed -i 's/%s/%s/' /etc/nsswitch.conf"%(nsswitch_group,'group: files winbind'))
        
#       cp_nsswitch_stat,cp_nsswitch_out=commands.getstatusoutput\
#       ("salt-cp '*' /etc/nsswitch.conf /etc/nsswitch.conf")
#       nsswitch_out=cp_nsswitch_out.split('\n')
#       for check_nsswitch in nsswitch_out:
#           if not check_nsswitch.find("True")>=0:
#               icfs_util.error('033','/etc/nsswitch.conf')
                
#       domain_split = domain.upper().split('.')[0]
#       smb='''
# [global]
# idmap uid = 25000-30000
# idmap gid = 25000-30000
# idmap config %s : backend = rid
# idmap config %s : range = 100000-499999
# workgroup = %s
# password server = %s
# realm = %s
# security = ads
# template shell = /bin/bash
# winbind use default domain = true
# winbind offline logon = false
# server string = Samba Server Version %s
# log file = /var/log/samba/log.%s
# max log size = 50
# passdb backend = tdbsam
# load printers = yes
# cups options = raw
# [homes]
# comment = Home Directories
# browseable = no
# writable = yes
#       '''%(domain_split,domain_split,domain_split,dcip,domain.upper(),'%v','%m')
#       f_smb=open('/etc/samba/smb.conf','w')
#       f_smb.write(smb)
#       f_smb.close()
#       cp_smb_stat,cp_smb_out=commands.getstatusoutput\
#       ("salt-cp '*' /etc/samba/smb.conf /etc/samba/smb.conf")
#       smb_out=cp_smb_out.split('\n')
#       for check_smb in smb_out:
#           if not check_smb.find("True")>=0:
#               icfs_util.error('033','/etc/samba/smb.conf')
        
#       commands.getoutput("salt '*' cmd.run 'ntpdate -u %s'"%(dcip))
#       commands.getoutput("salt '*' cmd.run 'ntpdate -u %s'"%(dcip))
#       commands.getoutput("echo 'session    required     pam_mkhomedir.so skel=/etc/skel umask=0077' >> /etc/pam.d/system-auth ")
#       commands.getoutput("echo 'session    required     pam_mkhomedir.so skel=/etc/skel umask=0077' >> /etc/pam.d/sshd ")
#       cp_system_auth_stat,cp_system_auth_out=commands.getstatusoutput\
#       ("salt-cp '*' /etc/pam.d/system-auth /etc/pam.d/system-auth")
#       system_auth_out=cp_system_auth_out.split('\n')
#       for check_auth_out in system_auth_out:
#           if not check_auth_out.find("True")>=0:
#               icfs_util.error('033','/etc/pam.d/system-auth')
                
#       cp_sshd_stat,cp_sshd_out=commands.getstatusoutput\
#       ("salt-cp '*' /etc/pam.d/sshd /etc/pam.d/sshd")
#       sshd_out=cp_sshd_out.split('\n')
#       for check_ssd_out in sshd_out:
#           if not check_ssd_out.find("True")>=0:
#               icfs_util.error('033','/etc/pam.d/sshd')
        
#       smb_stat,smb_out = commands.getstatusoutput("salt '*' cmd.run 'service smb restart'")
#       # host_name_status,host_name_out = commands.getstatusoutput('hostname')
#       # if host_name_status != 0:
#           # print 'can not get hostname'
#           # copy_back()
#           # sys.exit(1)
#       one_host_stat,one_host_out = commands.getstatusoutput('net ads join -U %s%s'%(username+'%',password))
#       if one_host_stat != 0:
#           copy_back()
#           icfs_util.error('038')
#       join_stat,join_out = commands.getstatusoutput("salt '*' cmd.run 'net ads join -U %s%s;echo $?'"%(username+'%',password))
#       #print join_out
#       #restart winbind must behind join ad ,or winbind will dead
#       wbind_stat,wbind_out = commands.getstatusoutput("salt '*' cmd.run 'service winbind restart'")
#       test_out = commands.getoutput('id %s'%username)
#       if 'No such user' in test_out:
#           copy_back()
#           icfs_util.error('038')
#       # else:
#           # print "Congratulations! Join AD Domain successfully!"
