import logging

from ..models import TestResult, TestCase, TestRun
from metadash.models import db, get_or_create
from ..utils.xunit import Report

logger = logging.getLogger(__name__)


def create_testcase(result, testcase_name):
    testcase, _ = get_or_create(db.session, TestCase, name=testcase_name)
    result.testcase = testcase


def process_xml(xml_content):
    junit_report = Report()
    junit_report.loads(xml_content)

    junit_cases = junit_report.get_flatten_testcases_legacy()

    properties = junit_report.get_properties()
    details = {}

    # For very long string, submit as 'detail' for better performance
    for k in list(properties.keys())[:]:
        value = properties[k]
        if isinstance(value, (str, list)) and len(value) > 1024:
            details[k] = value
            properties.pop(k)

    testrun = TestRun.from_dict({
        "status": "RUNNING",  # XXX
        "name": properties.get('job_name') or properties.get('param-job_name', None),  # FIXME
        "timestamp": junit_report.start_time,
        "ref_url": (
            "%s#%s" % (
                properties.get('build_url') or properties.get('env-BUILD_URL', ''),
                properties.get('variant') or properties.get('param-qemu_pkg', 'rhel'))  # FIXME
            # Since rhel/rhev share the same url, add a hash suffix for a unique ref_url
            # Manual "ci run" have no build_url, send null instead
        ),
        "properties": properties,
        "details": details,
        "tags": [properties.get('variant') or 'rhel']  # FIXME
    })

    db.session.add(testrun)
    db.session.commit()
    db.session.refresh(testrun)

    testcases = set()
    for testcase in junit_cases:
        try:
            if testcase.is_skipped():
                result = 'SKIPPED'
            elif testcase.is_failure() or testcase.is_error():
                result = 'FAILED'
            else:
                result = 'PASSED'

            if testcase.name not in testcases:
                testcases.add(testcase.name)  # XXX
                testresult = TestResult()
                create_testcase(testresult, testcase.name)

                testresult.from_dict({
                    "testrun_uuid": testrun.uuid,
                    "testcase_name": testcase.name,
                    "ref_url": testcase.get_url(),
                    "duration": str(testcase.elapsed_sec),
                    "result": result,
                    "details": {
                        "system-out": testcase.stdout,
                        "system-err": testcase.stderr,
                        "failure": testcase.failure_message,
                        "error": testcase.error_message,
                        "skipped": testcase.skipped_message
                    },
                })

            db.session.add(testresult)
        except Exception:
            logger.exception("Got exception during parsing xml file, test case %s", testcase)

    db.session.commit()

    testrun.from_dict({
        "status": "FINISHED"
    })

    db.session.commit()
