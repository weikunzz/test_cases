"""
Hook the model to send metrics message
"""
import stomp
import json
import logging
import datetime

from .utils import ci_message

from metadash.event import on
from metadash.injector import require
from metadash.utils.umb import make_connection


testrun = require('testrun')


def submit_metrics(testrun):
    if testrun.properties.get('ci-metrics-data-submitted'):
        return
    job_name = testrun.name
    job_url = testrun.properties['job_url']
    build_url = testrun.ref_url
    arch = testrun.properties['arch']
    product = testrun.properties["product"]
    version = testrun.properties["version"]
    subtest = testrun.properties["variant"]
    nvr = testrun.properties['build']

    base_distro = "%s%s" % (product, version)

    try:
        message = testrun.properties.get('message') or testrun.details.get("message")
        if message == '{}':
            return
        message = ci_message.CIMessage(testrun.properties.get('message') or testrun.details.get("message"))
    except ci_message.CIMessageParseError:
        return
    else:
        brew_taskid = message.brew_taskid or ''
        nvr = message.nvr or nvr
        scratch = message.scratch or False

    if nvr and nvr.endswith('.%s' % arch):
        nvr = nvr.rstrip('.%s' % arch)

    ci_tier = 1 if scratch else 2
    build_type = "scratch" if scratch else "official"
    headers = {
        "CI_TYPE": "ci-metricsdata",
        "owner_id": "libvirt-ci",
    }

    body = {
        "trigger": "brew build",
        "team": "libvirt-ci",
        "recipients": "kasong, gsun",

        "component": nvr,
        "jenkins_job_url": job_url,
        "jenkins_build_url": build_url,
        "job_name": job_name,
        "CI_tier": ci_tier,
        "base_distro": base_distro,
        "brew_task_id": brew_taskid,
        "build_type": build_type,

        # Not used
        "logstash_url": "",
        "CI_infra_failure": "",
        "CI_infra_failure_desc": "",
        "note": "Submit by Metadash",
    }

    test_duration = 0
    for testresult in testrun.testresults:
        test_duration += testresult.duration

    body.update({
        "tests": [
            {
                "executor": "beaker",
                "subtest": subtest,
                "arch": arch,
                "executed": sum(testrun.results.values()) - testrun.results.get("SKIPPED", 0) - testrun.results.get("ERROR", 0),
                "passed": testrun.results.get("PASSED", 0),
                "failed": testrun.results.get("FAILED", 0),
            },
        ],
        "create_time": testrun.timestamp.isoformat(),
        "complete_time": (testrun.timestamp + datetime.timedelta(seconds=test_duration)).isoformat(),
    })

    json_msg = json.dumps(body, indent=4)
    logging.info("Sending message header:\n%s\n, body:\n%s\n",
                 json.dumps(headers, indent=4), json_msg)

    conn = stomp.Connection([('ci-bus.lab.eng.rdu2.redhat.com',
                              61613)], timeout=10)
    conn.start()
    conn.connect(login='ci-ops-central-jenkins',
                 passcode='tQrYdOHhBqOMJi/k')
    if stomp.__version__[0] < 4:
        # pylint: disable=no-value-for-parameter
        conn.send(message=json_msg, headers=headers,
                  destination='/topic/CI')
    else:
        conn.send(body=json_msg, headers=headers,
                  destination='/topic/CI')
    conn.disconnect()
    testrun.properties['ci-metrics-data-submitted'] = 'true'
    logging.info('Metrics message sent.')


def setup():
    @on(testrun, 'after_save')
    def submit_metrics_hook(mapper, connection, testrun):
        pass
        # if testrun.status == 'FINISHED' and testrun.ref_url is not None:
        #     submit_metrics(testrun)
