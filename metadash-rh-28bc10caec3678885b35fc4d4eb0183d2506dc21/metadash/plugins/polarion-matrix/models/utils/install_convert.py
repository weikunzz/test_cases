"""
Example Plugin, also used for testing and debug
"""
import re

from metadash.injector import require
testrun = require('testrun')

PPC_NAME_RE = 'the name of guest is (.+)'
PPC_VIDEO_RE = 'the video type of VM is (.+)'
PPC_GRAPH_RE = 'the graphic type of VM is (.+)'
PPC_IMAGE_RE = 'the installation method is (.+)'

INST_METHOD_RE = 'the installation method is (\w+)'
GUESTNAME_RE = 'guestname: (\w+)'
PARAM_RE = ' ([\w]+), (i386|x86_64), (\w+)\(network\), (\w+)\(disk\), (\w+), (\w+), (\w+), (\w+)\(storage\)'

"RHEL7-80620"  # - [Matrix] Install a guest via iso method
"RHEL7-82418"  # - [Matrix] Install a guest via pxe method
"RHEL7-80624"  # - [Matrix] Install a guest via http method
"RHEL7-80625"  # - [Matrix] Install a guest via ftp method
"RHEL7-80626"  # - [Matrix] Install a guest via nfs method
"RHEL7-80627"  # - [Matrix] Install a guest via boot.iso method


def convert_single_testresult(testrun, testresult):
    testarch = testrun.properties['arch']
    if testarch != 'x86_64':
        return None, {}
    matched = re.findall(PARAM_RE, testresult.details['system-out'])
    method = re.findall(INST_METHOD_RE, testresult.details['system-out'])
    method = re.findall(INST_METHOD_RE, testresult.details['system-out'])
    guestname = re.findall(GUESTNAME_RE, testresult.details['system-out'])
    if method:
        method, = method
    if guestname:
        guestname, = guestname
    if matched:
        guestos, guestarch, nicdriver, hddriver, imageformat, graphic, video, diskpath = matched[0]
    else:
        return None, {}

    testcase_name = testresult.testcase_name
    if testcase_name.startswith('rhev') or testcase_name.startswith('rhel'):
        testcase_name = testcase_name[5:]

    # XXX: Ehgggg.....
    if testcase_name.endswith('install_linux_bootiso'):
        workitem = 'RHEL7-80627'
    elif testcase_name.endswith('install_linux_net_remote'):
        if method == 'nfs':
            workitem = 'RHEL7-80626'
        elif method == 'ftp':
            workitem = 'RHEL7-80625'
        elif method == 'http':
            workitem = 'RHEL7-80624'
    elif testcase_name.endswith('install_linux_pxe'):
        workitem = 'RHEL7-82418'
    elif testcase_name.endswith('install_windows_cdrom'):
        workitem = 'RHEL7-80620'
    elif testcase_name.endswith('install_windows_iso'):
        workitem = 'RHEL7-80620'
    elif testcase_name.endswith('install_ubuntu'):
        workitem = 'RHEL7-80620'
    elif testcase_name.endswith('install_linux_iso'):
        workitem = 'RHEL7-80620'

    return workitem, {
        'guestname': guestname,
        'guestos': guestos,
        'guestarch': guestarch,
        'hddriver': hddriver,
        'nicdriver': nicdriver,
        'imageformat': imageformat,
        'graphic': graphic,
        'video': video,
        'diskpath': diskpath
    }
