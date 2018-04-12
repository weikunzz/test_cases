"""
Query Teiid bugzilla database and report x86 bugs to JIRA
"""
import collections
import logging
import os

from libvirt_ci import jira
from libvirt_ci import teiid

from libvirt_ci.data import RESOURCE_PATH

LOGGER = logging.getLogger(__name__)

# RHEL6 project key is LIBVIRTSIX
# RHEL7 project key is LIBVIRTSEV
# RHEL7.4 parent is LIBVIRTSEV-853
# RHEL7.3 parent is LIBVIRTSEV-380
# RHEL7.2 parent is LIBVIRTSEV-1
# RHEL6.9 parent is LIBVIRTSIX-236
# JIRA issue dictionary, 1 key has 2 values.
# key means libvirt version in which the bug fixed in,
# values includes (jira project, jira parent)

PRODUCTS = {
    'rhel-6.9': ('LIBVIRTSIX', 'LIBVIRTSIX-236'),
    'rhel-7.2': ('LIBVIRTSEV', 'LIBVIRTSEV-1'),
    'rhel-7.3': ('LIBVIRTSEV', 'LIBVIRTSEV-380'),
    'rhel-7.4': ('LIBVIRTSEV', 'LIBVIRTSEV-853'),
    'rhel-7.5': ('LIBVIRTSEV', 'LIBVIRTSEV-1236')
}

GROUPS = [
    ('xuzhang', 'yisun', 'lmen', 'hhan', 'jiyan', 'meili'),
    ('yalzhang', 'lhuang', 'jishao', 'chhu', 'jinqi'),
    ('zpeng', 'fjin', 'yafu', 'yanqzhan', 'lizhu'),
    ('weizhan', 'lcheng', 'dzheng')
]
QA_DEFAULT = u'chhu'


def get_on_qa_bugs():
    """
    Get a list of all monitoring ON_QA bugs from Teiid
    """
    LOGGER.info("Retrieving latest ON_QA bugs from Teiid")
    sqlfile = os.path.join(
        RESOURCE_PATH, 'psql', 'RHEL-libvirt-x86-open-bugs.sql')
    new_teiid = teiid.Teiid()
    results = new_teiid.run_sql_file(sqlfile)

    if len(results) == 1:
        on_qa_bugs = results[0]
    else:
        raise Exception("Expect 1 SQL commands in file %s. Found %d." %
                        (sqlfile, len(results)))
    LOGGER.info("Found %s ON_QA bugs", len(on_qa_bugs))
    return on_qa_bugs


def get_issues(jira_inst):
    """
    Get a list of all existing JIRA issues tracking ON_QA bugs
    """
    LOGGER.info("Retrieving ON_QA tracking issues from JIRA")
    jira_projects = collections.defaultdict(list)
    for _, (project, parent_id) in PRODUCTS.items():
        jira_projects[project].append(parent_id)

    issues = []
    fields = None
    for project, parent_ids in jira_projects.items():
        jql = "status != Done AND parent in (%s)" % ','.join(parent_ids)
        issues.extend(jira_inst.search_issues(project, jql, fields=fields))
    LOGGER.info("Found %s issues", len(issues))
    return issues


def prepare_issue_dict(bug_info):
    """
    Prepare the JIRA issue dictionary according to bug info
    """
    bug_id, bug_desc, fixed_in, fixed_product, qa_email = bug_info

    for product in PRODUCTS.keys():
        if fixed_product.startswith(product):
            fixed_product = product

    jira_project, parent_id = PRODUCTS[fixed_product]

    issue_dict = {
        'issuetype': {
            'name': 'Sub-task',
        }
    }

    issue_dict['project'] = {'key': jira_project}
    issue_dict['parent'] = {'id': parent_id}

    assignee = QA_DEFAULT
    if qa_email and (qa_email != 'virt-bugs@redhat.com'):
        assignee = qa_email.split('@')[0]

    if not fixed_in:
        issue_dict['summary'] = u"[ON_QA] Bug %s - %s" % (bug_id, bug_desc)
    else:
        issue_dict['summary'] = u"[ON_QA] [%s] Bug %s - %s" % (
            fixed_in, bug_id, unicode(bug_desc, "utf-8"))
    issue_dict['description'] = "https://bugzilla.redhat.com/show_bug."
    issue_dict['description'] += "cgi?id=%s" % bug_id
    issue_dict['priority'] = {'name': 'Normal'}
    issue_dict['assignee'] = {'name': unicode(assignee, "utf-8")}
    return issue_dict


def find_or_create_issue(jira_inst, issues, bug_id, issue_dict):
    """
    Find JIRA issue tracking specific bug. Create a new one if not found.
    """
    match_issue = None
    for issue in issues:
        summary = issue.fields.summary
        if str(bug_id) in summary:
            LOGGER.info("Found issue %s for bug %s", issue, bug_id)
            match_issue = issue
            break
    if not match_issue:
        LOGGER.info("Create issue for bug %s", bug_id)
        match_issue = jira_inst.create_issue(issue_dict)
    return match_issue


def update_issue(jira_inst, match_issue, issue_dict):
    """
    Update existing JIRA issue if specific fields not accord with expectation.
    """
    # Update JIRA issue if summary changed
    old_summary = match_issue.fields.summary
    update_dict = {}
    if issue_dict['summary'] != old_summary:
        LOGGER.info("Update summary of %s", match_issue)
        LOGGER.info("    From: %s", old_summary)
        LOGGER.info("    To  : %s", issue_dict['summary'])
        update_dict['summary'] = issue_dict['summary']

    # Update JIRA issue if assignee changed
    old_assignee = match_issue.fields.assignee.name
    assignee = issue_dict['assignee']['name']
    if assignee != old_assignee:
        LOGGER.info("Update assignee of %s", match_issue)
        LOGGER.info("    From: %s", old_assignee)
        LOGGER.info("    To  : %s", assignee)
        update_dict['assignee'] = issue_dict['assignee']

    if update_dict:
        match_issue.update(fields=update_dict)

    # Update JIRA watcher list if group lead not in watchers
    group_lead = None
    for group in GROUPS:
        if assignee in group:
            group_lead = group[0]
            break
    if not group_lead:
        LOGGER.error("Assignee %s is not found in list", assignee)

    watchers = [w.key for w in jira_inst.jira_.watchers(match_issue).watchers]
    if group_lead not in watchers:
        LOGGER.info("Adding group lead %s to %s watchers list",
                    group_lead, match_issue)
        jira_inst.add_watcher(match_issue, group_lead)


# pylint: disable=unused-argument
def run(params):
    """
    Check and create issues for x86-64 ON_QA bugs in JIRA
    """
    jira_inst = jira.Jira()

    # Get all ON_QA bugs from Teiid
    bug_list = get_on_qa_bugs()

    # Get all ON_QA bug JIRA issues
    issues = get_issues(jira_inst)

    # Update every found bug in JIRA
    for bug_info in bug_list:
        try:
            bug_id, _, _, _, _ = bug_info

            # Prepare the issue related info from bug info
            issue_dict = prepare_issue_dict(bug_info)

            # Find matching JIRA issue or create new one
            match_issue = find_or_create_issue(
                jira_inst, issues, bug_id, issue_dict)

            # Update existing bug if inconsistent found
            update_issue(jira_inst, match_issue, issue_dict)
        # pylint: disable=broad-except
        except Exception as exc:
            LOGGER.error("Skip processing bug %s because of an error: %s",
                         bug_info, exc)
            continue


def parse(parser):
    """
    Parse arguments for report x86 bugs to JIRA
    """
