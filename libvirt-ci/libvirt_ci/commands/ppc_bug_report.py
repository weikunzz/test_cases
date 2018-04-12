"""
Query teiid bugzilla database and report ppc bugs to jira
"""
import logging

from libvirt_ci import teiid
from libvirt_ci import jira

LOGGER = logging.getLogger(__name__)


def update_ppc_issue(jira_inst, project, parent, bug_list, rpl_list):
    """
    Check and create issues for new ppc bugs in Jira
    """
    issue_dict = {
        'project': {
            'key': project,
        },
        'issuetype': {
            'name': 'Sub-task',
        },
        'assignee': {
            'name': 'dzheng',
        },
        'labels': [],
    }

    jql = "status != Done AND parent in (%s)" % parent
    jira_issues = jira_inst.search_issues(project, jql)

    for bug_id, bug_desc, version in bug_list:
        rpl = False
        issue_dict['summary'] = "Bug %s - %s" % (bug_id, bug_desc)
        issue_dict['description'] = "https://bugzilla.redhat.com/show_bug."
        issue_dict['description'] += "cgi?id=%s" % bug_id
        issue_dict['parent'] = {'id': parent}
        issue_dict['priority'] = {'name': 'Normal'}
        version = 'RHEL' + version
        issue_dict['labels'].append(version)

        if str(bug_id) in rpl_list[1]:
            issue_dict['summary'] = 'RPL ' + issue_dict['summary']
            issue_dict['priority'] = {'name': 'Critical'}
            issue_dict['description'] += "\nIn RPL bug %s" % rpl_list[0]
            issue_dict['description'] += " depend list"
            rpl = True

        issue_exist = False
        for issue in jira_issues:
            summary = issue.fields.summary
            if str(bug_id) in summary:
                LOGGER.info("Skip create issue as %s already exist for "
                            "bug: %s", issue.key, bug_id)
                issue_exist = True
                if rpl:
                    if "RPL" not in issue.fields.summary:
                        LOGGER.info("Update issue summary")
                        issue.update(summary=issue_dict['summary'])
                    if issue.fields.priority.name != "Critical":
                        LOGGER.info("Update issue priority")
                        issue.update(priority=issue_dict['priority'])
                    if issue.fields.description != issue_dict['description']:
                        LOGGER.info("Update issue description")
                        issue.update(description=issue_dict['description'])
                break

        if not issue_exist:
            LOGGER.info("Create issue for bug %s", bug_id)
            jira_inst.create_issue(issue_dict)


def run(params):
    """
    Main function for reporting ppc bugs to Jira
    """
    new_teiid = teiid.Teiid()
    if params.sqlfile:
        results = new_teiid.run_sql_file(params.sqlfile)
        if len(results) == 3:
            oth_list = results[0]
            on_qa = results[1]
            rpl_list = results[2]
        else:
            raise Exception("Expect 3 SQL commands in file %s. Found %d." %
                            (params.sqlfile, len(results)))
    else:
        oth_list, on_qa, rpl_list = new_teiid.run_sql_cmd(params.sql)

    jira_inst = jira.Jira()
    project = params.project

    rpl_list = [rpl_list[0][0], rpl_list[0][1].split(',')]

    parent = params.onqa_parent
    LOGGER.info("Check ON_QA bug issues under parent %s", parent)
    update_ppc_issue(jira_inst, project, parent, on_qa, rpl_list)

    parent = params.other_parent
    LOGGER.info("Check Other bug issues under parent %s", parent)
    update_ppc_issue(jira_inst, project, parent, oth_list, rpl_list)


def parse(parser):
    """
    Parse arguments for report ppc bugs to jira
    """
    parser.add_argument(
        '--project', dest='project', action='store',
        default='LIBVIRTPPC',
        help='The jira project name.')
    parser.add_argument(
        '--onqa-parent', dest='onqa_parent', action='store',
        default='LIBVIRTPPC-104',
        help='The jira issue parent.')
    parser.add_argument(
        '--other-parent', dest='other_parent', action='store',
        default='LIBVIRTPPC-102',
        help='The jira issue parent.')

    exclusive_group = parser.add_mutually_exclusive_group(required=True)
    exclusive_group.add_argument(
        '--sqlfile', dest='sqlfile', action='store',
        help='The sql file path to query teiid database.')
    exclusive_group.add_argument(
        '--sql', dest='sql', action='store',
        help='The sql command string to query teiid database.')
