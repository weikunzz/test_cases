"""
Report test case results to libvirt-dashboard
"""

import logging
import requests

from libvirt_ci import report

LOGGER = logging.getLogger(__name__)


def split_tags_param(tags):
    ret = []
    for tag in tags.split(","):
        tag = tag.strip()
        if not tag:
            continue
        ret.append(tag)
    return ret


def run(params):
    """
    Main function for reporting dashboard
    """
    junit_report = report.Report()
    junit_report.load(params.junit)
    junit_cases = junit_report.get_flatten_testcases_legacy()
    junit_properties = junit_report.get_properties()
    junit_timestamp = junit_report.start_time
    junit_keys = junit_report.get_report_keys()

    url = params.url

    def require_param(name):
        ret = params.__dict__.get(name) or junit_keys.get(name)
        if not ret:
            raise Exception("Missing paramater %s" % name)
        return ret

    res = requests.post(url + '/api/run/', json={
        "name": require_param('job_name'),
        "component": require_param('component'),
        "build": require_param('build'),
        "product": require_param('product'),
        "version": require_param('version'),
        "arch": require_param('arch'),
        "type": require_param('test_type'),
        "framework": require_param('test_framework'),
        "ci_url": "%s#%s" % (require_param('build_url'), require_param('variant')),
        "date": params.date or junit_timestamp.isoformat(),
        "project": params.project,
        "description": params.description,
        "properties": junit_properties,
        "tags": split_tags_param(params.tags) + [require_param('variant')]
    })

    # pylint: disable=no-member
    if res.status_code == 400 and not params.force:
        LOGGER.error('Test run already exits.')
        return 1
    elif res.status_code != requests.codes.ok:
        LOGGER.error('Failed create test run with: %s', res.text)
    else:
        LOGGER.debug("Test run created: %s", res.json())

    run_id = res.json()['id']

    for case in junit_cases:
        res = requests.post(url + '/api/run/' + str(run_id) + "/auto/", json={
            "output": case.stdout,
            "skip": case.skipped_message,
            "failure": case.failure_message or case.error_message,
            "time": str(case.elapsed_sec),
            "case": case.name,
        })
        # pylint: disable=no-member
        if res.status_code != requests.codes.ok:
            LOGGER.error('Failed submit test result for case %s, with %s',
                         case.name, res.text)

    if params.auto_submit_to_polarion:
        res = requests.get(url + '/trigger/run/' + str(run_id) + "/submit")
        # pylint: disable=no-member
        if res.status_code != requests.codes.ok:
            LOGGER.error('Failed submit to polarion with: '
                         '%s', res.text)
        else:
            LOGGER.debug("Response from dashboard: %s", res.json())


def parse(parser):
    """
    Parse arguments for reporting result to Jira.
    """
    parser.add_argument(
        '--dashboard-url', dest='url', action='store',
        default='http://libvirt-dashboard.lab.eng.pek2.redhat.com',
        help='Dashboard API URL')
    parser.add_argument(
        '--auto-submit-to-polarion', dest='auto_submit_to_polarion', action='store_true',
        help='Submit the test run to polarion automatically.')
    parser.add_argument(
        '--junit', dest='junit', action='store', required=True,
        help='Path of junit test result storing in')
    parser.add_argument(
        '--description', dest='description', action='store',
        default='',
        help='Description of the test run')
    parser.add_argument(
        '--tags', dest='tags', action='store',
        help='Tags of the test run, eg. "rhev upstream", split by \',\', spaces or newline')
    parser.add_argument(
        '--force', dest='force', action='store_true',
        help='Wether force upload result to dashboard')

    # Data that could be read from report
    parser.add_argument(
        '--name', dest='name', action='store',
        help='Test job name')
    parser.add_argument(
        '--component', dest='component', action='store',
        help='Which component tested')
    parser.add_argument(
        '--build', dest='build', action='store',
        help='Component build number')
    parser.add_argument(
        '--product', dest='product', action='store',
        help='Which product tested.')
    parser.add_argument(
        '--version', dest='version', action='store',
        help='Product version')
    parser.add_argument(
        '--arch', dest='arch', action='store',
        help='CPU Architecture')
    parser.add_argument(
        '--test-type', dest='test_type', action='store',
        help='Test type (acceptance or function)')
    parser.add_argument(
        '--framework', dest='framework', action='store',
        help='Test framework (avocado-vt, test-api, etc.)')
    parser.add_argument(
        '--project', dest='project', action='store', default='RedHatEnterpriseLinux7',
        help='Which polarion project belongs to')
    parser.add_argument(
        '--date', dest='date', action='store',
        help='Datetime in isoformat. Default to current local time')
    parser.add_argument(
        '--build-url', dest='build_url', action='store',
        help='URL for the test run on Jenkins.')
