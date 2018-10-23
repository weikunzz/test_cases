#!/usr/bin/python
#coding:utf-8
# -*- copyright -*-
'''
change list
modify at 2016-12-28 by huper. add run_command() function
modify at 2017-1-10 by huper. modify run_command() add 2>/dev/null
'''
import os
import sys
import commands
import re
import datetime
import platform
#from ConfigParser import ConfigParser
from ConfigParser import ConfigParser,DEFAULTSECT,ParsingError,MissingSectionHeaderError
import RemoteRunner
import json
import sqlite3
import fcntl
import subprocess
import time
import threading

hosts = []

current_user = commands.getoutput('whoami')

SSHConnectTimeout = 2
DEBUG = 0
def run_command(comm, node=None,debug=0):
    global DEBUG
    if debug:
        DEBUG = debug
    result = None
    commstart = '\033[1;32;40m'
    valuestart = '\033[1;33;40m'
    end = '\033[0m'
    begintime = 0
    endtime = 0
    if node:
        if DEBUG:
            print commstart, "[DEBUG info] remote commands: ", ("ssh -o ConnectTimeout=%s -o ConnectionAttempts=2 -o PasswordAuthentication=no -o StrictHostKeyChecking=no 'root@%s' \"%s\" 2>/dev/null" % (SSHConnectTimeout, node, comm)), end
            begintime = datetime.datetime.now()
        result = commands.getstatusoutput("ssh -o ConnectTimeout=%s -o ConnectionAttempts=2 -o PasswordAuthentication=no -o StrictHostKeyChecking=no 'root@%s' \"%s\" 2>/dev/null " % (SSHConnectTimeout, node, comm))
    else:
        if DEBUG:
            print commstart, "[DEBUG info] local commands: ", comm, end
            begintime = datetime.datetime.now()
        result = commands.getstatusoutput(comm)
    if DEBUG:
        endtime = datetime.datetime.now()
        print valuestart, "run time: " + str((endtime - begintime).seconds) + "s", end
        print valuestart, "[DEBUG info]", result, end
    return result


def error(*num):
    
    error_num = {
        
        '001': 'Error(001):Can not communicate with ypbind',
        '002': 'Error(610):Invalid input!',
        '003': 'Error(003):The username already exist',
        '004': 'Error(004):The groupname already exist',
        '005': 'Error(005):Quit failed at host %s ' % (num[-1]),
        '006': 'Error(006):Can not connect to domainname %s' % (num[-1]),
        '007': 'Error(007):The user does not exist at host %s' % (num[-1]),
        '008': 'Error(008):The usergroup does not exist at host %s' % (num[-1]),
        '009': 'Error(009):Can not delete a system group',
        '010': 'Error(010):Can not delete a system user',
        '011': 'Error(011):Please input the username',
        '012': 'Error(012):Permission denied,please try the root user',
        '013': 'Error(002):Can not modify a system user',
        '014': 'Error(014):Test failed ',
        '015': 'Error(015):The username already exist as ad domain user',
        '016': 'Error(016):The groupname already exist as ad domain group',
        '017': 'Error(017):Please join NIS first',
        '018': 'Error(018):No such file or grep nothing',
        '019': 'Error(019):Failed,the group has some users now at host %s'%(num[-1]),
        '020': 'Error(020):The group can not be a system group',
        '021': 'Error(021):The dn can not be more than 255 characters',
        '022': 'Error(022):The domain name must be between 1 and 32 characters',
        '023': 'Error(023):The password must be between 8 and 32 characters',
        '024': 'Error(024):The username must be between 1 and 32 characters',
        '025': 'Error(025):Can not get host\'s ip',
        '026': 'Error(026):The host can not connect to Server',
        '027': 'Error(027):The domain name is %s' % (num[-1]),
        '028': 'Error(028):Failed! The baseDN is %s,please check your input' % (num[-1]),
        '029': 'Error(029):Failed to start ypbind',
        '030': 'Error(030):Can not find the service of ypbind ',
        '031': 'Error(307):Salt service down in %s ' % (num[-1]),
        '032': 'Error(032):The format of IP address has error',
        # '033':'Error(033):Failed to copy %s to other host'%(num[-1]),
        # '034':'Error(034):Failed to configure Kerberos service at host %s'%(num[-1]),
        # '035':'Error(035):Failed to configure Winbind service at host %s'%(num[-1]),
        # '036':'Error(036):Failed to idmap SMB at host %s'%(num[-1]),
        # '037':'Error(037):Failed to enable winbind at host %s'%(num[-1]),
        '038': 'Error(038):Failed to join AD!please check your configuration',
        '039': 'Error(039):Failed to restart windbind at host %s' % (num[-1]),
        # '040':'Error(040):failed Configuring ntp at host %s'%(num[-1]),
        '041': 'Error(041):Clock skew too great at host %s' % (num[-1]),
        '042': 'Error(042):Failed to query ldap,please check whether to joined the ldap domain',
        '043': 'Error(043):Can not find ldap server\'s IP or port ',
        '044': 'Error(044):Can not find ldap users ,please check the configuration ',
        # '045':'Error(045):Could not obtain winbind domain name ',
        '046': 'Error(046):Port must less than 65535 ',
        '047': 'Error(047):The group name must be between 1 and 32 characters',
        '048': 'Error(048):Invalid user name %s' % (num[-1]),
        '049': 'Error(049):Invalid group name %s' % (num[-1]),
        '057': 'Error(057):Remote host %s is not accessable' % (num[-1]),
        '299': 'Error(299):Invalid salt service',
        # common error number
        '601': 'Error(610): Invalid input!',

        '3001': 'Error(3001):Commands ipmitool error',
        '3002': 'Error(3002):Please check your node name',
        '3003': 'Error(3003):Commands ifconfig error',
        '3005': 'Error(3005):Read file rack_info.txt error',
        '3004': 'Error(3004):Please set DNS first',
        '3006': 'Error(3006):This type of Tasks is maximizing',
        '3007': 'Error(3007):The device is not SmartRack',
        '3008': 'Error(3008):Command ip link show error',
        '3009': 'Error(3009):The device is SmartRack,parameter --node should be smartrack',
        '3010': 'Error(3010): Commands dmidecode error: %s' % num[-1]

    }
    print error_num.get(num[0])
    sys.exit(1)


def object_error(*args):
    if args[0] == 3400:
        print 'Error(3400): invalid port %s, please check' % args[0]
    if args[0] == 3401:
        print "Error(3401): can't open %s, please check" % args[0]
    if args[0] == 3402:
        print "Error(3402): unexpect error %s, please check" % args[0]
    if args[0] == 3403:
        print "Error(3403): command [%s] execute fail, failinfo: %s" % (args[1], args[2])
    if args[0] == 3404:
        print "Error(3404): create pool fail, fail info: %s" % args[0]
    if args[0] == 3405:
        print "Error(3405): get rados gateway service status fail"
    if args[0] == 3406:
        print "Error(3406): unknown service status %s" % args[0]
    elif args[0] == 3509:
        print("Error(3509): execute cmd %s fail, fail info: %s!" % (args[0], args[0]))
    sys.exit(1)


def nfs_error(num):
    if num==701:
        print "Error(701): No such path"
    if num==702:
        print "Error(702): Invalid ACL input!"
    if num==703:
        print "Error(703): Synchronization configuration file failed"
    if num==705:
        print "Error(705): The Path already exists"
    if num==706:
        print "Error(706): This NFS-Path not exists"
    if num==707:
        print "Error(707): User not exists"
    if num==708:
        print "Error(708): User is exists"
    if num==610:
        print "Error(610): Invalid input!"
    if num==715:
        print "Error(715): Host not exists"
    if num==716:
        print "Error(716): Invalid ip address"
    if num==717:
        print "Error(717): Invalid groupname"
    if num==721:
        print "Error(721): Invalid path"
    if num==299:
        print "Error(299): Invalid salt service"

def del_dir_error(num):
    if num==500:  
        sys.exit(1)
    if num==501:
        print "del_dir_error(501): Already exists",
    if num==610:
        print "del_dir_error(610): Invalid input! ",
    if num==503:
        print "del_dir_error(503): Failed",
    if num==504:
        print "del_dir_error(504): File system not mount",
    if num==505:
        print "del_dir_error(505): Failed setfattr pool and directory, try again later",
    if num==401:
        print "del_dir_error(401): No exists",
    if num==506:
        print "Error(506): Directory include subdirectory",
    if num==507:
        print "del_dir_error(507): NFS shared directory",
    if num==508:
        print "del_dir_error(508): CIFS shared directory",
    if num==509:
        print "del_dir_error(509): The system is cleaning up the data,please try again later!",
    if num==299:
        print "del_dir_error(299): Invalid salt service"
    if num == 556:
        print "Error(556): Cluster is not health, can't execute OSD capacity balance"
    if num == 557:
        print "Error(557): The number of OSD is not same between different nodes in cluster, can't execute OSD capacity balance"
    if num == 558:
        print "Error(558): The weight in crushmap is not same between different nodes in cluster, can't execute OSD capacity balance"
    if num == 559:
        print "Error(559): In 4+2:1 scenario, the mount of disk should be at least 24 so that can reach the OSD weight balance"

def cifs_create_error(num,*description):
    if num==024:
        print 'Error(024):The username must be between 1 and 32 characters'
    if num==100:
        print "Error(100): Can not find path in cluster file system!"
    if num==110:
        print "Error(110): Failed to mount icfs-fuse for %s"%description
    if num==120:
        print "Error(120): Cifs's share name %s has existed"%description
    if num==121:
        print "Error(121): Cifs's share name %s not exist"%description
    if num==125:
        print "Error(125): Cifs's share path not exist"
    if num==126:
        print "Error(126): Cifs's share user %s has existed"%description
    if num==127:
        print "Error(127): Cifs's share user %s not exist"%description
    if num==203:
        print "Error(203): Don't support batch operation for path"
    if num==205:
        print "Error(205): Don't support batch operation for acl"
    if num==206:
        print "Error(206): Don't support batch operation for share name"
    if num==210:
        print "Error(210): Local user %s not exist"%description
    if num==215:
        print "Error(215): Local group %s not exist"%description
    if num==220:
        print "Error(220): Domain user %s not exist"%description
    if num==225:
        print "Error(225): Domain group %s not exist"%description
    if num==240:
        print "Error(240): Samba share mode doesn't support"
    if num==250:
        print "Error(250): acl_value input wrong!"
    if num==255:
        print "Error(255): Failed to set acl for user"
    if num==299:
        print "Error(299): Invalid salt service"
    if num==300:
        print "Error(300): Failed to restart smb for %s"%description
    if num==301:
        print "Error(301): Failed to restart nmb for %s"%description
    if num==302:
        print "Error(302): Failed to reload smb configuration for %s"%description
    if num==303:
        print "Error(303): Failed to synchronize smb.conf for %s"%description
    if num==305:
        print "Error(305): SMB unrecognized service"
    if num==306:
        print "Error(306): NMB unrecognized service"
    if num==307:
        print "Error(307): Salt service down in %s"%description
    if num==308:
        print "Error(308): Invalid salt-key"
    if num==310:
        print "Error(310): Failed to get ADC server name/ip"
    if num==610:
        print "Error(610): Invalid input!"
    if num==721:
        print "Error(721): Invalid path"
    sys.exit(1)        

def user_admin_errors(num):
    if num==3101:
        print "Error(3101): This user already exists"
    if num==3102:
        print "Error(3102): Database operation failure"
    if num==3103:
        print "Error(3103): This user does not exists"
    if num==3104:
        print "Error(3104): Can not delete the super administrator"
    if num==3105:
        print "Error(3105): The number of users beyond the maximum 10"
    if num==3106:
        print "Error(3106): The old password is error"
    sys.exit(1)


def acl_error(num, *description):
    if num == 610:
        print "Error(610): Invalid input! "
    elif num == 1700:
        print "Error(1700): User not exist"
    elif num == 1701:
        print "Error(1701): Group not exist"
    elif num == 1702:
        print "Error(1702): Invalid ACL value"
    elif num == 1703:
        print "Error(1703): Directory not exist"
    elif num == 1704:
        print "Error(1704): File not exist"
    elif num == 1705:
        print "Error(1705): Set ACL failed: %s" % description
    elif num == 1706:
        print "Error(1706): Get ACL failed: %s" % description
    elif num == 1707:
        print "Error(1707): Delete ACL failed: %s" % description
    elif num == 1708:
        print "Error(1708): Can not delete mask when ACL for other user or group exist"
    elif num == 1709:
        print "Error(1709): ACL function not enable in /etc/icfs/icfs.conf"
    else:
        print "Error(1399): Unknown error"
    sys.exit(1)


# get local normal user min id
def get_min_uid():
    dist_name, dist_version, dist_id = platform.linux_distribution()
    return 1000 if dist_version.startswith("7.") else 500


def get_hots():
    global hosts
    hosts_stat,hosts_out = commands.getstatusoutput("cat /etc/hosts |grep -v '#'")
    if hosts_out == '':
        error('025')
    else:
        hosts_list = hosts_out.split()
        for i in range(len(hosts_list)):
            if re.match(r"^([1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-4])\.([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])\.([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])\.([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])$",hosts_list[i]):
                hosts.append(hosts_list[i])
                if '127.0.0.1' in hosts :
                    hosts.remove('127.0.0.1')

def salt_run():
    salt_ck=commands.getoutput("service salt-master status")
    if "unrecognized service" in salt_ck or "stopped" in salt_ck :
        commands.getoutput("/usr/bin/icfs-admin-log --level 0 --module %s --info %s"%('Salt','Invalid salt service'))
        error('299')
    salt_down_out = commands.getoutput("salt-run manage.down")
    if salt_down_out != '':
        if 'YPBINDPROC_DOMAIN: Domain not bound' in salt_down_out:
            commands.getoutput("salt '*' cmd.run 'service ypbind stop'")
        else:
            smb_down_r=salt_down_out.replace("\n",",")
            smb_down_str=smb_down_r.lstrip(",")
            commands.getoutput("/usr/bin/icfs-admin-log --level 0 --module '%s' --info '%s%s'"%('Salt','Salt service down',smb_down_str))
            error('031',smb_down_str)

def user_name_format(name):
    if len(name) > 32:
        error('024')

    if re.match(r"^[a-zA-Z0-9\._][a-zA-Z0-9\._-]{0,31}$", name) == None:
        error('048', name)

def group_name_format(group_name):
    if len(group_name) > 32:
        error('047')

    if re.match(r"^[a-zA-Z0-9\._][a-zA-Z0-9\._-]{0,31}$", group_name) == None:
        error('049', group_name)


def passwd_format(passwd):
    if len(passwd) < 8 or len(passwd) > 32:
        error('023')

    # valid characters: letters numbers space `~!@#$%^&*()_=\|[]{}<>;:'",./?+-
    if re.match(r"^[a-zA-Z0-9 `~!@#$%^&*()_=\\|[\]{}<>;:'\",./?+-]+$", passwd) is None:
        error('002')


def ip_format(ip):
    # ip_list = ip.split('.')
    # ip1 = ip.strip()
    # if re.findall(r'[^\d.]',ip1) != [] or '' in ip_list  or len(ip_list) != 4 or re.findall(r'^[0]',ip1) != [] :
        # error('002')
    # elif re.findall(r'^00',ip_list[1]) != [] or re.findall(r'^00',ip_list[2]) != [] or re.findall(r'^00',ip_list[3]) != []:
        # error('002')
    # elif  not  0<int(ip_list[0])<=255 or int(ip_list[1])>255 or int(ip_list[2])>255 or int(ip_list[3])>255 or ip1 == '0.0.0.0' or ip1 == '255.255.255.255':
        # error('002')
    if not re.match(r"^([1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-4])\.([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])\.([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])\.([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])$",ip) :
        error('032')

def domain_format(domain):
    if len(domain) > 32:
        error('022')
    elif  re.findall(r'^[a-zA-Z]',domain) ==[] or  re.findall(r'[^\d]',domain) ==[] or \
        re.findall('[.]\Z',domain) !=[] or re.findall('[^\w.]',domain) !=[]:
        error('002')
        
def port_format(port):
    if re.findall(r'[^\d]',port) !=[]:
        error('002')
    elif int(port) > 65535:
        error('046')
        
def dn_format(dn):
    if len(dn) > 255:
        error('021')
    else:
        pattern = re.compile(r'^([a-zA-Z]+=[^,=\s]+,)*[a-zA-Z]+=[^,=\s]+$')
        if pattern.match(dn) == None:
            error('002')
        
def ping_all(ip):
    salt_run()
    # filter salt stderror so that output can be parsed correctly
    ping_stat,ping_out = commands.getstatusoutput("salt '*' cmd.run 'ping -c 1 %s' 2>/dev/null|grep transmitted|awk '{print $4}'"%(ip))
    if '0' in ping_out :
        error('026','')
    # get_mon_stat,get_mon_out = commands.getstatusoutput("cat /etc/icfs/icfs.conf |grep mon_host |awk '{print $3}'")
    # if get_mon_stat != 0 :
        # print get_mon_out
        # sys.exit(1)
    # elif get_mon_out == '' or get_mon_out == None:
        # error('025')
    # else:
        # mon_list = get_mon_out.split(',')
        # for mon in mon_list:
            # ping_stat,ping_out = commands.getstatusoutput("salt -S '%s' cmd.run 'ping -c 2 %s ;echo $?'"%(mon,ip))
            # ping_out_stat = ping_out.split('\n')[-1].strip()
            # if ping_out_stat != '0':
                # error('026',mon)
                
#use ':'to replace '=' When  configParser the samba file               
class NewConfigParser(ConfigParser) :
    """Act same as ConfigParser except that it consider = as the separator between key and value"""
    NEW_OPTCRE = re.compile(
        r'(?P<option>[^=\s][^=]*)'            # very permissive!
        r'\s*(?P<vi>[=])\s*'                  # any number of space/tab,
                                              # followed by separator
                                              # (only =), followed
                                              # by any # space/tab
        r'(?P<value>.*)$'                     # everything up to eol
        )
        
    def _read(self, fp, fpname):
        """Parse a sectioned setup file.

        The sections in setup file contains a title line at the top,
        indicated by a name in square brackets (`[]'), plus key/value
        options lines, indicated by `name: value' format lines.
        Continuations are represented by an embedded newline then
        leading whitespace.  Blank lines, lines beginning with a '#',
        and just about everything else are ignored.
        """
        cursect = None                            # None, or a dictionary
        optname = None
        lineno = 0
        e = None                                  # None, or an exception
        while True:
            line = fp.readline()
            if not line:
                break
            lineno = lineno + 1
            line = line.strip()                  # Strip left space when parse the smb.conf 
            # comment or blank line?
            if line.strip() == '' or line[0] in '#;':
                continue
            if line.split(None, 1)[0].lower() == 'rem' and line[0] in "rR":
                # no leading whitespace
                continue
            # continuation line?
            if line[0].isspace() and cursect is not None and optname:
                value = line.strip()
                if value:
                    cursect[optname] = "%s\n%s" % (cursect[optname], value)
            # a section header or option header?
            else:
                # is it a section header?
                mo = self.SECTCRE.match(line)
                if mo:
                    sectname = mo.group('header')
                    if sectname in self._sections:
                        cursect = self._sections[sectname]
                    elif sectname == DEFAULTSECT:
                        cursect = self._defaults
                    else:
                        cursect = self._dict()
                        cursect['__name__'] = sectname
                        self._sections[sectname] = cursect
                    # So sections can't start with a continuation line
                    optname = None
                # no section header in the file?
                elif cursect is None:
                    raise MissingSectionHeaderError(fpname, lineno, line)
                # an option line?
                else:
                    mo = self.NEW_OPTCRE.match(line)
                    if mo:
                        optname, vi, optval = mo.group('option', 'vi', 'value')
                        if vi == '=' and ';' in optval:
                            # ';' is a comment delimiter only if it follows
                            # a spacing character
                            pos = optval.find(';')
                            if pos != -1 and optval[pos-1].isspace():
                                optval = optval[:pos]
                        optval = optval.strip()
                        # allow empty values
                        if optval == '""':
                            optval = ''
                        optname = self.optionxform(optname.rstrip())
                        cursect[optname] = optval
                    else:
                        # a non-fatal parsing error occurred.  set up the
                        # exception but keep going. the exception will be
                        # raised at the end of the file and will contain a
                        # list of all bogus lines
                        if not e:
                            e = ParsingError(fpname)
                        e.append(lineno, repr(line))
        # if any parsing errors occurred, raise an exception
        if e:
            raise e


# IcfsVersion class
class IcfsVersion:
    """transform version string to listed numbers"""
    def __init__(self, version_string):
        self._ver_list = []
        version_string = re.sub("[^\d.]", "", version_string)
        sub_list = version_string.split(".")
        sub_list = [i for i in sub_list if i != ""]
        for sub_version in sub_list:
            self._ver_list.append(int(sub_version))

    @classmethod
    def current_version(cls):
        ver_output = commands.getoutput("icfs -v | awk '{print $3}'")
        return IcfsVersion(ver_output)

    # compare function
    def __cmp__(self, other):
        if not isinstance(other, IcfsVersion):
            raise TypeError, "can't cmp other type to IcfsVersion"
        self_len = len(self._ver_list)
        other_len = len(other._ver_list)
        min_len = min(self_len, other_len)
        for i in range(min_len):
            if self._ver_list[i] > other._ver_list[i]:
                return 1
            elif self._ver_list[i] < other._ver_list[i]:
                return -1

        if self_len > other_len:
            return 1
        elif self_len < other_len:
            return -1
        else:
            return 0


# return value example: ['host1', 'host2', 'host3']
def get_remote_host_list():
    try:
        return RemoteRunner.get_host_list()
    except Exception, err:
        print "Error(052): Failed to get remote hosts list"
        print err
        sys.exit(1)


# tgt:  '*' stands all hosts, 'node1,node2,node3' stands a list of hosts
# return value: { node_name1: {'status': status}, node_name2: 'status': status}, ... }
#      such as: { 'node1': {'status': True},
#                 'node2': {'status': False},
#                 'node3': {'status': True} }
#       status: True-reachable False-not reachable
def run_remote_ping(tgt):
    try:
        return RemoteRunner.run_ping(tgt)
    except Exception, err:
        print "Error(053): Failed to test connections to remote hosts"
        print err
        sys.exit(1)


# tgt:  '*' stands all hosts, 'node1,node2,node3' stands a list of hosts
# cmd:  commnad to run
# return value: { node_name1: {'retcode': retcode, 'stdout': stdout, 'stderr': stderr}, ... }
#      such as: { 'node1': {'retcode': 0, 'stdout': 'abc', 'stderr': ''},
#                 'node2', {'retcode': 1, 'stdout': '', 'stderr': 'error'},
#                 'node3', {'retcode': -1, 'stdout': '', 'stderr': 'no return'} }
#      retcode: 0:success 1:failed -1:not accessable
def run_remote_cmd(tgt, cmd):
    try:
        return RemoteRunner.run_cmd(tgt, cmd)
    except Exception, err:
        print "Error(054): Failed to run command on remote hosts"
        print err
        sys.exit(1)


# tgt:  '*' stands all hosts, 'node1,node2,node3' stands a list of hosts
# src:  source file path
# dest: destination file path
# return value: { node_name1: {'retcode': retcode, 'retout': retout}, ... }
#      such as: { 'node1': {'retcode': 0, 'retout': ''},
#                 'node2', {'retcode': 1, 'retout': 'error'},
#                 'node3', {'retcode': -1, 'retout': 'no return'} }
#      retcode: 0:success 1:failed -1:not accessable
def run_remote_copy(tgt, src, dest):
    try:
        return RemoteRunner.run_copy(tgt, src, dest)
    except Exception, err:
        print "Error(055): Failed to copy file to remote hosts"
        print err
        sys.exit(1)


# tgt:  '*' stands all hosts, 'node1,node2,node3' stands a list of hosts
# src:  source file path
# dest: destination file path
# return value: True-success  False-failed
def run_remote_copy_with_rollback(tgt, src, dest):
    try:
        return RemoteRunner.run_copy_with_rollback(tgt, src, dest)
    except Exception, err:
        print "Error(055): Failed to copy file to remote hosts"
        print err
        sys.exit(1)


class CollectThread(threading.Thread):
    def __init__(self, p):
        super(CollectThread, self).__init__()
        self.p = p
        self.stdout = ""
        self.stderr = ""

    def run(self):
        self.stdout, self.stderr = self.p.communicate()


def kill_subprocess(sub_pid):
    import psutil
    import signal
    import os
    try:
        p = psutil.Process(sub_pid)
    except psutil.NoSuchProcess:
        return

    children = p.children(recursive=True)
    children.append(p)
    for child in children:
        try:
            os.kill(child.pid, signal.SIGKILL)
        except OSError:
            # do nothing when process does not exist anymore
            pass


# cmd: command to run on LOCALHOST
# return value: {'retcode': returncode, 'stdout': standard output, 'stderr': standard error}
#      such as: {'retcode': 0, 'stdout': 'abc', 'stderr': ''}
def run_local_cmd(cmd, shell=True, timeout=0):
    """
    run local command, support timeout
    :param cmd: command strings
    :param shell:
    :param timeout: timeout flag , time accuracy is 0.01 seconds. default timeout=0: don't return until command run over
    :return: {'retcode': returncode, 'stdout': standard output, 'stderr': standard error}
             such as: {'retcode': 0, 'stdout': 'abc', 'stderr': ''}
    """
    # p is running:               p.poll()=None,  type NoneType
    # p is killed by p.kill():    p.poll()=-9,    type int
    # p is successed:             p.poll()=0,     type int
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell)
    # wait process timeout seconds
    t = CollectThread(p)
    t.setDaemon(True)
    t.start()
    if timeout > 0:
        t.join(timeout=timeout)
        if t.isAlive():
            try:
                kill_subprocess(p.pid)
            except Exception:
                pass
            return {"retcode": 1, "stdout": "", "stderr": "command is timeout. " + cmd}
    else:
        t.join()

    # get command stdour
    stdout = t.stdout
    stderr = t.stderr
    # get retcode
    retcode = p.returncode
    if p.stdout:
        p.stdout.close()
    if p.stderr:
        p.stderr.close()
    if p.stdin:
        p.stdin.close()
    stdout = stdout.rstrip("\n")
    stderr = stderr.rstrip("\n")
    return {"retcode": retcode, "stdout": stdout, "stderr": stderr}


def con_db():  # remember to close the connection and cursor when calling this method
    connect_db = sqlite3.connect('/usr/local/db/tasks.db', timeout=15)  # if not exists so ,create it!
    cur_db = connect_db.cursor()
    cur_db.execute('''CREATE TABLE IF NOT EXISTS task(
        id integer primary key,
        name varchar,
        state varchar,
        process varchar,
        username varchar,
        start_time varchar)''')

    return connect_db, cur_db


# adjust if the number of osd of every node in cluster is same
# input
def if_osd_num_same(n):
    virtual_nodes = []
    nodes_osd = {}
    if IcfsVersion.current_version() >= IcfsVersion("3.5.0.0"):
        # get osd number
        status, output = commands.getstatusoutput("icfs node ls -f json 2>/dev/null")
        if not status:
            nodes_osd = dict(json.loads(output)['osd'])
        else:
            print output
            return False, False, 0
    else:
        status, output = commands.getstatusoutput(
            "cat /etc/hosts|grep -E '([0-9]{1,3}[\.]){3}[0-9]{1,3}'|sed '1d'|awk '{print $2}'")
        if not status:
            nodes = output.split('\n')
        else:
            print output
            return False, False, 0
        # add the virtual host name in nodes
        if 1 == n:
            for node in nodes:
                virtual_nodes.append("%s_n1" % node)
            nodes = nodes + virtual_nodes
        status, output = commands.getstatusoutput("icfs osd tree -f json 2>/dev/null")
        if not status:
            temp_list = json.loads(output)['nodes']
            for osd in temp_list:
                dict_osd = dict(osd)
                if 'host' == dict_osd['type'] and dict_osd['name'] in nodes:
                    nodes_osd[dict_osd['name']] = dict_osd['children']
        else:
            print output
            return False, False, 0

    osd_nums = [len(node_osd) for node_osd in nodes_osd.values()]
    osd_nums.sort()
    # don't have different osd number
    if 1 == len(set(osd_nums)):
        return True, True, osd_nums[0]
    else:
        return True, False, osd_nums[0]


def if_crush_weight_same(n):
    # get osd number
    nodes_osd = {}
    nodes_weight = []
    virtual_host_num = []
    virtual_nodes = []
    if IcfsVersion.current_version() >= IcfsVersion("3.5.0.0"):
        status, output = commands.getstatusoutput("icfs node ls -f json 2>/dev/null")
        if not status:
            nodes_osd = dict(json.loads(output)['osd'])
        else:
            print output
            return False, False, 0
    else:
        status, output = commands.getstatusoutput(
            "cat /etc/hosts|grep -E '([0-9]{1,3}[\.]){3}[0-9]{1,3}'|sed '1d'|awk '{print $2}'")
        if not status:
            nodes = output.split('\n')
        else:
            print output
            return False, False, 0
        # if the erase model and n==1 then need to add the virtual host name in nodes
        if 1 == n:
            for node in nodes:
                virtual_nodes.append("%s_n1" % node)
            nodes = nodes + virtual_nodes
        status, output = commands.getstatusoutput("icfs osd tree -f json 2>/dev/null")
        if not status:
            temp_list = json.loads(output)['nodes']
            for osd in temp_list:
                dict_osd = dict(osd)
                if 'host' == dict_osd['type'] and dict_osd['name'] in nodes:
                    nodes_osd[dict_osd['name']] = dict_osd['children']
        else:
            print output
            return False, False, 0

    # get osd tree
    status, output = commands.getstatusoutput("icfs osd tree -f json 2>/dev/null")
    if not status:
        osd_list = json.loads(output)['nodes']
        for node in nodes_osd.values():
            weight_sum = 0
            for osd_id in node:
                for osd in osd_list:
                    dict_osd = dict(osd)
                    if 'osd.%d' % osd_id == dict_osd['name']:
                        weight_sum += float(dict_osd['crush_weight'])
                    elif 'host' == dict_osd['type'] and re.match(".+_n1$", dict_osd['name']) is not None:
                        virtual_host_num.append(re.match(".+_n1$", dict_osd['name']).group(0))
            nodes_weight.append(weight_sum)
        # don't have different osd number
        if 1 == len(set(nodes_weight)):
            return True, True, len(virtual_host_num)
        else:
            return True, False, len(virtual_host_num)
    else:
        print output
        return False, False, 0


def if_cluster_normal():
    # get cluster status
    status, output = commands.getstatusoutput("icfs -s 2>/dev/null | grep -w health")
    if not status:
        cluster_status = output.split()[1]
        if "HEALTH_OK" == cluster_status:
            return True, True
        else:
            return True, False
    else:
        print output
        return False, False


def osd_capacity_balance_erasure(k, m, n, pool_name, task_start_time, fd, path):
    # get osd number
    ret_osd_same, if_same, osd_num = if_osd_num_same(n)
    if 1 == n and 4 == k and m == 2:
        if ret_osd_same and osd_num < 24:
            commands.getoutput("/usr/local/ism/Agent/src/Common/icfs-admin-log --level 0 --module '%s' --info '%s'" % (
                "Create_Dir:osd_capacity_balance_erasure(" + path + ")",
                'Error(559): In 4+2:1 scenario, the mount of disk should be at least 24'))
            del_dir_error(559)
            return 1
        elif not ret_osd_same:
            commands.getoutput("/usr/local/ism/Agent/src/Common/icfs-admin-log --level 0 --module '%s' --info '%s'" % (
                "Create_Dir:osd_capacity_balance_erasure(" + path + ")",
                'call if_osd_num_same return fail'))
            return 1
    # get PG number
    pg_number = 0
    status, output = commands.getstatusoutput("icfs osd dump 2>/dev/null | grep -w %s" % pool_name)
    if not status:
        pg_number = int(output.split('pg_num ')[1].split()[0])
    else:
        commands.getoutput("/usr/local/ism/Agent/src/Common/icfs-admin-log --level 0 --module '%s' --info '%s'" % (
            "Create_Dir:osd_capacity_balance_erasure(" + path + ")",
            'icfs osd dump execute fail:%s' % output))
        return 1
    # get node number
    node_num = 0
    # Venus has not icfs node ls so need to do more thing
    current_ver = IcfsVersion.current_version()
    if current_ver >= IcfsVersion("3.5.0.0"):
        status, output = commands.getstatusoutput("icfs node ls -f json 2>/dev/null")
        if not status:
            node_num = len(dict(json.loads(output)['osd']))
        else:
            commands.getoutput(
                "/usr/local/ism/Agent/src/Common/icfs-admin-log --level 0 --module '%s' --info '%s'" % (
                    "Create_Dir:osd_capacity_balance_erasure(" + path + ")",
                    'icfs node ls -f json execute fail:%s' % output))
            return 1
    else:
        status, output = commands.getstatusoutput(
            "cat /etc/hosts|grep -E '([0-9]{1,3}[\.]){3}[0-9]{1,3}'|sed '1d'|awk '{print $2}'")
        if not status:
            nodes = output.split('\n')
            node_num = len(nodes)
        else:
            commands.getoutput(
                "/usr/local/ism/Agent/src/Common/icfs-admin-log --level 0 --module '%s' --info '%s'" % (
                    "Create_Dir:osd_capacity_balance_erasure(" + path + ")",
                    'execute cat /etc/hosts fail: %s' % output))
            return 1

    # if node number equal to k+m number and the fault domain is not specified (default:host),
    # need to adjudge weight and osd number
    if 0 == n:
        if k + m == node_num:
            # adjudge osd num
            if ret_osd_same and not if_same:
                log_to_event_log(0, "Create_Dir:osd_capacity_balance_erasure(" + path + ")" if path
                                 else "expand re-weight",
                                 "Error(557): The number of OSD is not same between different nodes in cluster, "
                                 "can not execute OSD capacity balance")
                del_dir_error(557)
                return 1
            # adjudge crushmap weight
            ret, if_weight_same, virtual_host_num = if_crush_weight_same(n)
            if ret and not if_weight_same:
                log_to_event_log(0, "Create_Dir:osd_capacity_balance_erasure(" + path + ")" if path
                                 else "expand re-weight( %s )" % pool_name,
                                 "Error(558): The weight in crushmap is not same between different nodes in cluster, "
                                 "can not execute OSD capacity balance")
                del_dir_error(558)
                return 1
            elif not ret:
                log_to_event_log(0, "Create_Dir:osd_capacity_balance_erasure(" + path + ")" if path
                                 else "expand re-weight( %s )" % pool_name, 'call if_crush_weight_same return fail')
                return 1
    elif 1 == n:
        if k + m == node_num * 2:
            # adjudge osd num
            if ret_osd_same and not if_same:
                log_to_event_log(0, "Create_Dir:osd_capacity_balance_erasure(" + path + ")" if path
                                 else "expand re-weight( %s )" % pool_name,
                                 "Error(557): The number of OSD is not same between different nodes in cluster, "
                                 "can not execute OSD capacity balance")
                del_dir_error(557)
                return 1
            # adjudge crushmap weight
            ret, if_weight_same, virtual_host_num = if_crush_weight_same(n)
            if DEBUG:
                log_to_event_log(2, "Create_Dir:osd_capacity_balance_erasure(" + path + ")" if path
                                 else "expand re-weight( %s )" % pool_name,
                                 "call if_crush_weight_same re %d if_weight_same %d virtual_host_num %d" % (
                                     ret, if_weight_same, virtual_host_num)
                                 )
            if ret and not if_weight_same:
                log_to_event_log(0, "Create_Dir:osd_capacity_balance_erasure(" + path + ")" if path
                                 else "expand re-weight( %s )" % pool_name,
                                 "Error(558): The weight in crushmap is not same between different nodes in cluster, "
                                 "can not execute OSD capacity balance")
                del_dir_error(558)
                return 1
            elif not ret:
                log_to_event_log(0, "Create_Dir:osd_capacity_balance_erasure(" + path + ")" if path
                                 else "expand re-weight( %s )" % pool_name, 'call if_crush_weight_same return fail')
                return 1

    # lock the commit action
    fcntl.flock(fd, fcntl.LOCK_EX)
    con, cur = con_db()
    # adjudge the version
    cur.execute("UPDATE task SET process='70' WHERE start_time='%s'" % task_start_time)
    con.commit()

    # close
    cur.close()
    con.close()
    # unlock
    fcntl.flock(fd, fcntl.LOCK_UN)

    if current_ver > IcfsVersion("3.5.2.0"):
        # use new method
        status, output = commands.getstatusoutput("reweight_by_crushtool.sh %d %d %s"
                                                  % (k+m, pg_number, pool_name))
        if "Reweight SUCCESS" in output:
            log_to_event_log(2, "Create_Dir:osd_capacity_balance_erasure(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name, 'OSD reweight result: Reweight SUCCESS')
        else:
            log_to_event_log(0, "Create_Dir:osd_capacity_balance_erasure(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name, 'reweight_by_crushtool.sh execute fail: %s' % output)
            return 1
    else:
        if current_ver < IcfsVersion("3.5.0.0"):
            # if venus need to execute on command first
            status, output = commands.getstatusoutput("icfs osd pool set %s canbalance 1" % pool_name)
            if status:
                log_to_event_log(0, "Create_Dir:osd_capacity_balance_erasure(" + path + ")" if path
                                 else "expand re-weight( %s )" % pool_name,
                                 "icfs osd pool set %s canbalance 1 execute fail: %s" % (pool_name, output))
                return 1
        # use the old method
        status, output = commands.getstatusoutput("reweight_pool_osd_by_pg.sh %s" % pool_name)
        if "balance successfully" in output:
            log_to_event_log(2, "Create_Dir:osd_capacity_balance_erasure(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name, 'OSD reweight result: Reweight SUCCESS')
        else:
            log_to_event_log(0, "Create_Dir:osd_capacity_balance_erasure(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name,
                             'reweight_pool_osd_by_pg.sh execute fail: %s' % output)
            return 1
    return 0


def osd_capacity_balance_replicate(replicate_num, pool_name, task_start_time, fd, path):
    pg_number = 0
    # get PG number
    status, output = commands.getstatusoutput("icfs osd dump 2>/dev/null | grep %s" % pool_name)
    if not status:
        pg_number = int(output.split('pg_num ')[1].split()[0])
    else:
        log_to_event_log(0, "Create_Dir:osd_capacity_balance_replicate(" + path + ")" if path
                         else "expand re-weight( %s )" % pool_name, 'icfs osd dump fail:%s' % output)
        return 1
    # get node number
    node_num = 0
    # Venus has not icfs node ls so need to do more thing
    current_ver = IcfsVersion.current_version()
    if current_ver >= IcfsVersion("3.5.0.0"):
        status, output = commands.getstatusoutput("icfs node ls -f json 2>/dev/null")
        if not status:
            node_num = len(dict(json.loads(output)['osd']))
        else:
            log_to_event_log(0, "Create_Dir:osd_capacity_balance_replicate(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name, 'icfs node ls -f json execute fail:%s' % output)
            return 1
    else:
        status, output = commands.getstatusoutput(
            "cat /etc/hosts|grep -E '([0-9]{1,3}[\.]){3}[0-9]{1,3}'|sed '1d'|awk '{print $2}'")
        if not status:
            nodes = output.split('\n')
            node_num = len(nodes)
        else:
            log_to_event_log(0, "Create_Dir:osd_capacity_balance_replicate(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name, 'execute cat /etc/hosts fail: %s' % output)
            return 1

    # if node number equal to replicate number and the fault domain is not specified (default:host)
    if node_num == replicate_num:
        # adjudge osd num and can treat as erase: k+m:0 model
        ret, if_num_same, osd_num = if_osd_num_same(0)
        if ret and not if_num_same:
            log_to_event_log(0, "Create_Dir:osd_capacity_balance_replicate(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name,
                             "Error(557): The number of OSD is not same between different nodes in cluster, "
                             "can not execute OSD capacity balance")
            return 1
        elif not ret:
            log_to_event_log(0, "Create_Dir:osd_capacity_balance_replicate(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name, 'call if_osd_num_same return fail')
            return 1
        # adjudge crushmap weight
        ret, if_weight_same, virtual_host_num = if_crush_weight_same(0)
        if ret and not if_weight_same:
            log_to_event_log(0, "Create_Dir:osd_capacity_balance_replicate(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name,
                             "Error(558): The weight in crushmap is not same between different nodes in cluster,"
                             " can not execute OSD capacity balance")
            return 1
        elif not ret:
            log_to_event_log(0, "Create_Dir:osd_capacity_balance_replicate(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name, 'call if_crush_weight_same return fail')
            return 1
    # lock the commit action
    fcntl.flock(fd, fcntl.LOCK_EX)
    con, cur = con_db()
    # if the version is newer than 3.5.2.0, then we can use the second method(CRUSH analog)
    cur.execute("UPDATE task SET process='60' WHERE start_time='%s'" % task_start_time)
    con.commit()

    cur.close()
    con.close()
    # unlock
    fcntl.flock(fd, fcntl.LOCK_UN)

    if current_ver > IcfsVersion("3.5.2.0"):
        # use new method
        ret = run_local_cmd("reweight_by_crushtool.sh %d %d %s" % (int(replicate_num), pg_number, pool_name))
        status, output = commands.getstatusoutput("reweight_by_crushtool.sh %d %d %s"
                                                  % (int(replicate_num), pg_number, pool_name))
        if "Reweight SUCCESS" in output:
            log_to_event_log(2, "Create_Dir:osd_capacity_balance_replicate(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name, 'OSD reweight result: Reweight SUCCESS')
        else:
            log_to_event_log(0, "Create_Dir:osd_capacity_balance_replicate(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name,
                             'reweight_by_crushtool.sh execute fail, Info: %s' % output)
            return 1
    else:
        if current_ver < IcfsVersion("3.5.0.0"):
            # if venus need to execute on command first
            status, output = commands.getstatusoutput("icfs osd pool set %s canbalance 1" % pool_name)
            if status:
                log_to_event_log(0, "Create_Dir:osd_capacity_balance_replicate(" + path + ")" if path
                                 else "expand re-weight( %s )" % pool_name,
                                 "icfs osd pool set %s canbalance 1 execute fail: %s" % (pool_name, output))
                return 1
        # use the old method
        status, output = commands.getstatusoutput(" reweight_pool_osd_by_pg.sh %s" % pool_name)
        if "balance successfully" in output:
            log_to_event_log(2, "Create_Dir:osd_capacity_balance_replicate(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name, 'OSD reweight result: Reweight SUCCESS')
        else:
            log_to_event_log(0, "Create_Dir:osd_capacity_balance_replicate(" + path + ")" if path
                             else "expand re-weight( %s )" % pool_name,
                             'reweight_pool_osd_by_pg.sh execute fail, Info: %s' % output)
            return 1
    return 0


def get_virtual_hosts():
    try:
        cmd = "icfs osd tree 2>/dev/null | grep \".*_n1\""
        ret = run_local_cmd(cmd)
        if not ret["retcode"] or ret["retcode"] == 1:
            output = ret["stdout"]
            if not output:
                vr_hosts = []
            else:
                vr_hosts = [re.match("^.*host\s*(.*_n1)\s*$", item).group(1) for item in output.split('\n')]
            return 0, vr_hosts
        else:
            log_to_event_log(0, "get_virtual_hosts", "Error(3509): execute cmd %s fail, fail info: %s!"
                             % (cmd, ret["stderr"] if ret["stderr"] else ret["stdout"]))
            return 1, None
    except Exception, e:
        log_to_event_log(0, "get_virtual_hosts",e)
        return 1, None


# record the log to /usr/local/ism/Agent/src/Common/event.log
# level 0: error 1: warning 2: info
def log_to_event_log(level, mode_name, log_info):
    levels = ["Error", "Warning", "Info"]
    try:
        run_local_cmd("/usr/local/ism/Agent/src/Common/icfs-admin-log --level %d --module '%s' --info '%s'"
                      % (level, mode_name, log_info))
        with open("/var/log/icfs/icfs-admin-cluster.log", 'a') as log:
            log.write('%s %s [%s] info: %s \n'
                      % (str(datetime.datetime.now()), levels[level], mode_name, log_info))
    except:
        pass
# get fru info from cache file or ipmitool command
def get_fru_info(node=None):
    if not node:
        status, output = commands.getstatusoutput("cat /usr/bin/.fru_info.txt")
        if status == 0 and len(output) != 0:
            return output

        status, output = commands.getstatusoutput("ipmitool fru 2>/dev/null")
        if status != 0 or len(output) == 0:
            log_to_event_log(0, "get_fru_info", "get fru info fail %s" % output)
            return None

        try:
            with open("/usr/bin/.fru_info.txt", "w") as f:
                f.write(output)
        except IOError:
            pass

        return output
    else:
        ret = run_command("cat /usr/bin/.fru_info.txt", node)
        if not ret[0] and len(ret[1]) != 0:
            return ret[1]

        ret = run_command("ipmitool fru 2>/dev/null", node)
        if ret[0] != 0 or len(ret[1]) == 0:
            log_to_event_log(0, "get_fru_info", "get fru info fail %s" % ret[1])
            return None
        run_command("echo \\\"%s\\\" > /usr/bin/.fru_info.txt" % ret[1], node)

        return ret[1]


def record_node_SN(nodes):
    write_str = ""
    error_info = ""
    have_error = False
    for node in nodes:
        node = node.split(":")[0]
        # check if the file exist
        if os.path.exists("/usr/local/db/node_sn"):
            # check if the node exist in file
            ret = run_local_cmd("cat /usr/local/db/node_sn | grep -w %s" % node)
            if ret['retcode']:
                if ret['retcode'] == 1 and not ret['stdout']:
                    # can't find this node add it
                    pass
                else:
                    have_error = True
                    error_info += "unknown error %s" %(ret['stdout']+ret['stderr'])
                    continue
            else:
                continue
        sn = get_serila_number(node)
        if not sn:
            have_error = True
            error_info += "%s get serial number fail" % node
            continue
        # get ip according to the hostname
        ip_addr = run_local_cmd("cat /etc/hosts | grep -w %s" % node)
        if ip_addr['retcode'] or (not ip_addr['retcode'] and not ip_addr['stdout']):
            have_error = True
            error_info += "%s get ip according host fail" % node

        write_str += '%s:%s\n' % (ip_addr['stdout'].split()[0], sn)

    if have_error:
        return 1, error_info
    run_local_cmd("echo -e \"%s\" >> /usr/local/db/node_sn" % write_str)
    # sync the file
    run_remote_copy("*", "/usr/local/db/node_sn", "/usr/local/db/node_sn")
    return 0 ,None


# get product name from cache file or ipmitool command
def get_product_name():
    fru_info = get_fru_info()
    if fru_info is None:
        return None

    pattern = re.compile("^\s*Product Name\s*:\s*(.*?)\s*$")
    lines = fru_info.splitlines()
    for line in lines:
        m = pattern.match(line)
        if m is not None:
            return m.group(1)

    return None


# get serial number from cache file or ipmitool command
def get_serila_number(node):
    fru_info = get_fru_info(node)
    if fru_info is None:
        # try use dmidecode to find UUID
        ret = run_command("dmidecode -t system | grep -w UUID | awk -F ':' '{print \\$2}'", node)
        if not ret[0]:
            return ret[1]
        return None

    pattern = re.compile("^\s*Product Serial\s*:\s*(.*?)\s*$")
    lines = fru_info.splitlines()
    for line in lines:
        m = pattern.match(line)
        if m is not None:
            return m.group(1)

    return None


# get board mfg date from cache file or ipmitool command
def get_board_mfg_date():
    fru_info = get_fru_info()
    if fru_info is None:
        return None

    pattern = re.compile("^\s*Board Mfg Date\s*:\s*(.*?)\s*$")
    lines = fru_info.splitlines()
    for line in lines:
        m = pattern.match(line)
        if m is not None:
            return m.group(1)

    return None


# get rack info from cache file or ipmitool command
def is_rack():
    status, output = commands.getstatusoutput("cat /usr/bin/.rack_info.txt")
    if status == 0:
        return output.strip() == "rack"

    status, output = commands.getstatusoutput("ipmitool sdr")
    if status != 0:
        log_to_event_log(0, "is_rack", "get sdr info fail %s" % output)
        return None

    if "FAN" in output:
        commands.getstatusoutput("echo non-rack > /usr/bin/.rack_info.txt")
        return False
    else:
        commands.getstatusoutput("echo rack > /usr/bin/.rack_info.txt")
        return True
