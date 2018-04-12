"""
Report test case results to ResultsDB
"""

import resultsdb_api
import logging

from libvirt_ci import report

LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['git+https://pagure.io/taskotron/resultsdb_api.git@master']


def run(params):
    """
    Main function for reporting ResultsDB
    """
    junit_report = report.Report()
    junit_report.load(params.junit)
    junit_cases = junit_report.get_flatten_testcases_legacy()
    junit_timestamp = junit_report.start_time
    junit_keys = junit_report.get_report_keys()

    resultsdb = resultsdb_api.ResultsDBapi(params.url)

    def require_param(name):
        ret = params.__dict__.get(name) or junit_keys.get(name)
        if not ret:
            raise Exception("Missing paramater %s" % name)
        return ret

    def _get_or_create_group(description, **kwargs):
        """ Get or create group according to description and return the UUID """
        ref_url = kwargs.pop("ref_url", None)
        groups = resultsdb.get_groups(description=description, **kwargs)['data']
        if len(groups) == 0:
            group = resultsdb.create_group(description=description, ref_url=ref_url)
        elif len(groups) == 1:
            group = groups[0]
        elif len(groups) > 1:
            LOGGER.warn("Expeceted 1 group with description %s, found %d!",
                        description, len(groups))
            group = groups[0]
        else:
            raise RuntimeError("Invalid groups data %s" % groups)
        if ref_url and group["ref_url"] != ref_url:
            LOGGER.warn("Correcting 'ref_url' from %s to %s",
                        group['ref_url'], ref_url)
            resultsdb.update_group(group['uuid'], ref_url=ref_url)
        return group

    job_description = "%s-%s" % (require_param('job_name'),
                                 require_param('date') or junit_timestamp.isoformat())
    LOGGER.info("Job description %s", job_description)

    # No better way to define "tags" yet
    tag_groups = [_get_or_create_group(x) for x in params.tags.split(',') + [require_param('variant')] if x]
    job_group = _get_or_create_group(job_description, ref_url=params.build_url)

    # pylint: disable=no-member
    for case in junit_cases:
        # "output": case.stdout,
        # "skip": case.skipped_message,
        # "failure": case.failure_message or case.error_message,
        data = {
            "time": str(case.elapsed_sec),
            "component": require_param('component'),
            "build": require_param('build'),
            "product": require_param('product'),
            "version": require_param('version'),
            "arch": require_param('arch'),
            "framework": require_param('test_framework'),
            "variant": require_param('variant'),
            "project": params.project,
        }
        data = {k: v for k, v in data.items() if len(v) < 1023}

        resultsdb.create_result(
            "PASSED" if case.result == "PASS" else
            "FAILED" if case.result == "FAIL" else
            "NEEDS_INSPECTION",
            case.name,
            groups=[_['uuid'] for _ in [job_group] + tag_groups],
            ref_url=case.get_url(),
            **data
        )


def parse(parser):
    """
    Parse arguments for reporting result to Jira.
    """

    # Data that can only be parsed from command line
    parser.add_argument(
        '--api-url', dest='url', action='store',
        default='http://libvirt-dashboard.lab.eng.pek2.redhat.com/resultsdb/api/v2.0',
        help='Resultsdb API URL')
    parser.add_argument(
        '--junit', dest='junit', action='store', required=True,
        help='Path of junit test result storing in')
    parser.add_argument(
        '--project', dest='project', action='store', default='RedHatEnterpriseLinux7',
        help='Which polarion project belongs to')

    # Data that from report
    parser.add_argument(
        '--component', dest='component', action='store',
        help='Which component tested')
    parser.add_argument(
        '--framework', dest='framework', action='store',
        help='Test framework (avocado-vt, test-api, etc.)')
    parser.add_argument(
        '--tags', dest='tags', action='store', default='',
        help='Tags of the test run, eg. "rhev upstream", split by \',\', spaces or newline')
    parser.add_argument(
        '--date', dest='date', action='store',
        help='Datetime in isoformat. Default to current local time')
    parser.add_argument(
        '--name', dest='name', action='store',
        help='Test job name')
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
        '--build-url', dest='build_url', action='store',
        help='URL for the test run on Jenkins.')
    parser.add_argument(
        '--variant', dest='variant', action='store',
        help='Currently only for RHEL/RHEV')
