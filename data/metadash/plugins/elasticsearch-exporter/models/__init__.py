"""
Example Plugin, also used for testing and debug
"""
import requests
from metadash.async import task, update_task_info
from metadash.event import on
from metadash.injector import require


TestRun = require('testrun')


@task()
def export_testrun(uuid):
    testrun = TestRun.from_uuid(uuid)
    for testresult in testrun.testresults:
        update_task_info("Pushing data for test %s, testrun %s" % (testresult.testcase_name, testrun.uuid))
        requests.post('http://elasticsearch-elasticsearch.cloudapps.qe-ocp.libvirt.redhat.com/testresult/_doc/',
                      json=testresult.as_dict())


@task()
def export_all_testrun():
    step = 100
    pos = 0
    processed = 0
    testruns = TestRun.query.offset(pos).limit(step).all()
    while len(testruns) > 0:
        pos += step
        for testrun in testruns:
            for testresult in testrun.testresults:
                update_task_info("%s: Pushing data for test %s, testrun %s" % (processed, testresult.testcase_name, testrun.uuid))
                requests.post('http://elasticsearch-elasticsearch.cloudapps.qe-ocp.libvirt.redhat.com/testresult/_doc/',
                              json=testresult.as_dict())
                processed += 1


@on(TestRun, 'after_save')
def push_to_elastic(mapper, connection, target):
    if target.status == 'FINISHED':
        export_testrun.delay(target.uuid)
