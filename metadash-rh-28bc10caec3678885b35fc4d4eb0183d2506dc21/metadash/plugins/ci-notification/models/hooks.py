"""
Hook the model to send notification
"""
import logging

from .mail import send

from metadash.event import on
from metadash.injector import require

logger = logging.getLogger(__name__)

# TODO: Make strings configurable

METADASH_URL = "http://qed.lab.eng.pek2.redhat.com"

NOFIFY_TITLE = "[CI][{test_framework}][{result}] {nvr} brew task {brewid}"

NOTIFY_TEMPLATE = """
Brew task:      {brew_task}
Build target:   {os_tree}
Tested package: {package}
Build issuer:   {issuer}
Summary:        {metadash_url}
Result:         {test_result}
Arch:           {arch}

{extra}
--
By Libvirt-CI: https://libvirt-jenkins.rhev-ci-vms.eng.rdu2.redhat.com
Generate by Metadash: http://qed.lab.eng.pek2.redhat.com/dashboard
"""

TEST_FAILURE_HEADER = """
Failed tests:
"""

TEST_CASE_TEMPLATE = """

  {testcase} failed on:

    Detail: {testcase_ref_url}
    Error Message: {error_message}

"""


testrun = require('testrun')


def publish_notification(testrun):
    if testrun.properties.get('ci-notification-published'):
        return

    job_name = testrun.name
    job_url = testrun.properties['job_url']
    test_framework = testrun.properties['test_framework']
    build_url = testrun.ref_url
    arch = testrun.properties['arch']
    product = testrun.properties["product"]
    version = testrun.properties["version"]
    subtest = testrun.properties["variant"]
    nvr = testrun.properties['nvr']
    brewner = testrun.properties['brewner']
    brewid = testrun.properties["brewid"]

    results = testrun.results
    passed = int(results.get('PASSED', '0'))
    skipped = int(results.get('SKIPPED', '0'))
    failed = int(results.get('FAILED', '0'))

    base_distro = "%s-%s" % (product, version)

    if nvr and nvr.endswith('.%s' % arch):
        nvr = nvr.rstrip('.%s' % arch)

    result = None
    if passed:
        if not failed:
            result = 'PASSED'
    if failed:
        result = 'FAILED'

    if not brewner or not brewid or not nvr or not result:
        logger.error('Skipped sending CI nofitication due to lack of info')
        logger.error('brewner: "%s", brewid: "%s", nvr: "%s", result: "%s", results: "%s"', brewner, brewid, nvr, result, results)
        return

    if result == 'FAILED':
        extra = TEST_FAILURE_HEADER + '\n'.join(
            TEST_CASE_TEMPLATE.format(
                testcase=testresult.testcase_name,
                testcase_ref_url="{metadash_url}/test-results/testresult/{uuid}".format(
                    metadash_url=METADASH_URL, uuid=testresult.uuid),
                error_message=testresult.details.get('error', '')
            ) for testresult in testrun.testresults if testresult.result == 'FAILED'
        )
    else:
        extra = ""

    body = NOTIFY_TEMPLATE.format(
        brew_task=brewid,
        os_tree=base_distro,
        package=nvr,
        issuer=brewner,
        metadash_url='{metadash_url}/test-results/testrun/{uuid}/'.format(
            metadash_url=METADASH_URL, uuid=testrun.uuid),
        test_result=result,
        arch=arch,
        extra=extra
    )

    subject = NOFIFY_TITLE.format(
        test_framework=test_framework,
        result=result,
        nvr=nvr,
        brewid=brewid,
    )

    if send('platform-ci-notification@redhat.com', subject=subject, text=body):
        testrun.properties['ci-notification-published'] = 'true'
    else:
        testrun.properties['ci-notification-published'] = 'failed'


def setup():
    @on(testrun, 'after_save')
    def hook(mapper, connection, testrun):
        if testrun.status == 'FINISHED' and testrun.ref_url is not None:
            publish_notification(testrun)
