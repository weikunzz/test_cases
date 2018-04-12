"""
Report a Jira issue for each of the failed/skipped test case
This command is only used for reporting with XUnit file generated by
Libvirt-CI runner.
"""

import logging
import re

from jira.exceptions import JIRAError

from libvirt_ci import jira
from libvirt_ci import metadata
from libvirt_ci import report
from libvirt_ci import utils
from libvirt_ci import clustering

FALLBACK_OWNER = 'kasong'
DEFAULT_AUTO_OWNER = 'chwen'

LOGGER = logging.getLogger(__name__)


def parse_valid_test_cases(job_report, fail_thld):
    """
    Exit immediately if failure rate is higher than fail_thld,
    else filter all blacklisted and skipped test cases and return the rest.
    """
    all_test_cases = job_report.get_flatten_testcases()
    valid_test_cases = []
    fail_test_cases = []

    for case in all_test_cases:
        if case.message and not case.is_blacklisted() and not case.is_ignored():
            valid_test_cases.append(case)
            if case.is_failure() or case.is_error():
                fail_test_cases.append(case)

    fail_ratio = len(fail_test_cases) / len(all_test_cases)
    if fail_ratio > fail_thld / 100.0:
        LOGGER.error("Failure ratio %.2f%% (%d/%d) exceeded threshold %d%%. "
                     "Won't report to JIRA", fail_ratio * 100, len(fail_test_cases),
                     len(all_test_cases), fail_thld)
        exit(1)

    return valid_test_cases


def parse_report_properties(job_report):
    """
    Process a label string into a set of labels
    """
    props = job_report.get_report_keys()

    build_url = props.get('build_url')

    labels = set([
        'libvirt-ci',
        '%s%s' % (props['product'], props['version']),
        props['arch'],
        props['test_type'],
        props['test_framework'],
        props['component'],
        props['job_name'],
    ])

    feature = None
    jobs = metadata.Metadata('Jobs').fetch()
    for job in jobs:
        if props['test_name'] in job['Name']:
            feature = job['Feature']
            labels.add(unicode(feature))
            break

    return labels, feature, build_url


# Need to fix this pylint warning
# pylint: disable=too-many-locals
def _report_issue(message, issue, cases, labels, feature, build_url, params):
    def _make_description(message, cases, labels, result):
        description = ("(!) {color:#ffa500}*This is automatically managed "
                       "by libvirt CI. Please don't change it*{color}\n")
        description += ('The following cases are %s with similar reason:\n' %
                        result)
        description += '{code}%s{code}\n' % message.strip()
        for idx, case in enumerate(cases):
            if idx < 50:
                # Add test URL on Jenkins
                description += '* *[%s|%s]*\n** %s\n' % (
                    case.full_name, case.get_url(build_url), case.message)
            else:
                description += '* and %s more cases *\n' % (
                    len(cases) - idx)
                break
        # Add a line of labels
        description += '\n*%s*\n' % ' '.join('(on) ' + label
                                             for label in labels)
        return description

    def _update_issue_info(issue, labels, description, priority, assignee,
                           watchers):
        jira_srv = jira.Jira()
        # Comment existing Jira issue if matching one is found
        LOGGER.info("Commenting in existing issue <%s:%s>",
                    issue, issue.fields.summary)
        jira_srv.add_comment(issue, description)

        issue_info = {}
        old_labels = set(issue.fields.labels)
        new_labels = labels | old_labels

        if 'skipped' in labels and 'failed' not in labels:
            if issue.fields.status == 'Rejected':
                return LOGGER.info(
                    "Skipping update issue, as we don't update rejected issue"
                    "for skipped test cases.")

        if new_labels != old_labels:
            LOGGER.info("Updating labels of %s from %s to %s",
                        issue, list(old_labels), list(new_labels))
            issue_info['labels'] = list(new_labels)

        old_status = str(issue.fields.status)
        if old_status in ['Done', 'Closed']:
            new_status = 'To Do'
            LOGGER.info("Updating status of %s from '%s' to '%s'",
                        issue, old_status, new_status)
            jira_srv.transition_issue(issue, new_status)

            # Adjust priority if existing issue is already fixed before
            issue_info['priority'] = {'name': priority}

        # Update assignee only if not assigneed
        if not issue.fields.assignee:
            LOGGER.info("Issue %s have no assignee, assign to '%s'",
                        issue, assignee)
            issue_info['assignee'] = {'name': assignee}

        # Extend watchers
        old_watchers = jira_srv.get_watchers(issue)
        if old_watchers != watchers:
            jira_srv.add_watcher(issue,
                                 list(set(watchers) - set(old_watchers)))

        if issue_info:
            LOGGER.info('Updating issue %s with info %s', issue, issue_info)
            issue.update(issue_info)

    def _create_new_issue(message, labels, description, priority, assignee,
                          watchers):
        jira_srv = jira.Jira()
        summary = message
        # Jira issue summary max width is 255
        if len(summary) > 200:
            summary = summary[:200] + '...'
        LOGGER.info("Creating new JIRA issue: %s", summary)

        issue_dict = {
            'project': {
                'key': 'LIBVIRTAT',
            },
            'summary': summary,
            'description': description,
            'parent': {
                'id': 'LIBVIRTAT-19',
            },
            'priority': {
                'name': priority,
            },
            'issuetype': {
                'name': 'Sub-task',
            },
            'assignee': {
                'name': assignee,
            },
        }
        if labels:
            issue_dict['labels'] = list(labels)

        LOGGER.info('Creating issue with %s', issue_dict)
        issue = jira_srv.create_issue(issue_dict)

        if watchers:
            jira_srv = jira.Jira()
            jira_srv.add_watcher(issue, watchers)
        return issue

    def _get_priority(params, result):
        priority = 'Major'
        if result == 'failed':
            priority = params.fail_priority.capitalize()
        if result == 'skipped':
            priority = params.skip_priority.capitalize()
        return priority

    def _get_assignee_watchers(feature):
        feature = metadata.get_groups(['feature', 'automation']).get(feature)
        owners = [FALLBACK_OWNER]
        auto_owners = [DEFAULT_AUTO_OWNER]
        if feature:
            owners = utils.split(
                feature['Feature Owners']) or owners
            auto_owners = utils.split(
                feature['Automation Owner']) or auto_owners
        assignee = owners[0]
        watchers = set(owners + auto_owners)
        return assignee, watchers

    # for backward compatibility
    results = [
        'failed' if case.result == 'FAIL' else
        'skipped' if case.result == 'SKIP' else
        case.result.lower() for case in cases]

    labels = labels.copy()
    labels.update(results)

    common_result = max(set(results), key=results.count)
    description = _make_description(message, cases, labels, common_result)
    priority = _get_priority(params, common_result)

    assignee, watchers = _get_assignee_watchers(feature)

    assignee = params.assignee or assignee
    watchers = set([watcher.decode('utf8')
                    for watcher in utils.split(params.watchers)]) or watchers

    if issue:
        print(issue, labels, description, priority, assignee, watchers)
        _update_issue_info(issue, labels, description, priority, assignee,
                           watchers)
    else:
        issue = _create_new_issue(message, labels, description, priority,
                                  assignee, watchers)


def _get_classifier():
    classifier = clustering.Classifier()
    jira_srv = jira.Jira()

    jira_issues = jira_srv.search_issues(
        "LIBVIRTAT",
        'parent = LIBVIRTAT-19 AND labels = libvirt-ci',
    )

    for issue in jira_issues:
        description = issue.fields.description
        match = re.search(r"\{\{(.*)\}\}", description)
        if not match:
            match = re.search(r"\{code.*\}(.*)\{code\}", description)
        if not match:
            LOGGER.error("Can't find issue %s's pattern", issue)
            continue
        pattern = match.groups()[0]
        classifier.add(pattern, info={'issue': issue})
    return classifier


def run(params):
    """
    Main function for reporting Jira
    """
    junit_report = report.Report()
    junit_report.load(params.junit)

    reporting_cases = parse_valid_test_cases(junit_report, float(params.fail_thld))

    labels, feature_id, build_url = parse_report_properties(junit_report)

    if not feature_id:
        LOGGER.error("Can't find coresponding feature for this job.")
        if not params.assignee:
            LOGGER.error("Can't find an assignee.")
            exit(1)

    classifier = _get_classifier()

    for case in reporting_cases:
        classifier.add(case.message, info={'case': case})

    for message, entries in classifier.classes.items():
        issue = None
        cases = []
        for entry in entries:
            # Find the earliest issue since earliest come last in search result
            if 'issue' in entry:
                issue = entry['issue']
            if 'case' in entry:
                cases.append(entry['case'])
        if cases:
            try:
                _report_issue(message, issue, cases, labels, feature_id, build_url, params)
            except JIRAError:
                LOGGER.exception("Failed to create jira issue for cases: %s", cases)


def parse(parser):
    """
    Parse arguments for reporting result to Jira.
    """
    parser.add_argument(
        '--junit', dest='junit', action='store', required=True,
        help='Path of junit test result storing in')
    parser.add_argument(
        '--threshold', dest='threshold', action='store', default='0.6',
        help='Test result string comparing threshold')
    parser.add_argument(
        '--fail-priority', dest='fail_priority', action='store',
        default='blocker',
        help='Priority of created issue when job is failed.')
    parser.add_argument(
        '--skip-priority', dest='skip_priority', action='store',
        default='critical',
        help='Priority of created issue when job is skipped.')
    parser.add_argument(
        '--assignee', dest='assignee', action='store', default='',
        help='Assignee of jira issue to be reported, if not set will try to query feature owner as the assignee')
    parser.add_argument(
        '--watchers', dest='watchers', action='store', default='',
        help='Watchers of jira issue to be reported, if not set will try to query feature owner as the watcher')
    parser.add_argument(
        '--fail-threshold', dest='fail_thld', action='store',
        default='100',
        help='Threshold of failure percentage that above this will '
             'consider job as fail and do not report to JIRA')
