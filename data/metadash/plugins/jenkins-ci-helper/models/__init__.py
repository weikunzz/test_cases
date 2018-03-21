"""
Example Plugin, also used for testing and debug
"""
import requests
from metadash.event import on
from metadash.injector import require


testrun = require('testrun')


@on(testrun, 'after_save')
def fetch_testrun_console_text(mapper, connection, target):
    if target.status == 'FINISHED':
        ref_url = target.ref_url
        if ref_url and 'libvirt-jenkins.rhev-ci-vms.eng.rdu2.redhat.com' in ref_url:
            ref_url = ''.join(ref_url.split('#')[:-1]).rstrip('/')
            res = requests.get('{}/consoleText'.format(ref_url))
            if res.status_code == requests.codes.ok:
                target.details['console_text'] = res.text
            else:
                target.details['console_text'] = "Failed retriving console log with %s" % res.text
