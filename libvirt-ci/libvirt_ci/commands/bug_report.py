"""
Query teiid bugzilla database and report bugs to jira
"""
import logging
import os

from libvirt_ci import teiid
from libvirt_ci import jira

from libvirt_ci.data import RESOURCE_PATH

LOGGER = logging.getLogger(__name__)


REPORT_MAP = {
    'RHEL-7.4': {
        'rpl': '1395265',
        'product_id': '201',
        'component_id': '103761',
        'ppc': {
            'project': 'LIBVIRTPPC',
            'onqa_parent': 'LIBVIRTPPC-104',
            'other_parent': 'LIBVIRTPPC-102',
            'assignee': 'junli',
        },
    },
    'RHEL-7.5': {
        'rpl': '1469590',
        'product_id': '201',
        'component_id': '103761',
        's390': {
            'project': 'LIBVIRTPPC',
            'onqa_parent': 'LIBVIRTPPC-226',
            'other_parent': 'LIBVIRTPPC-225',
            'assignee': 'dzheng',
        },
        'ppc': {
            'project': 'LIBVIRTPPC',
            'onqa_parent': 'LIBVIRTPPC-104',
            'other_parent': 'LIBVIRTPPC-102',
            'assignee': 'junli',
        },
    },
}


def run(params):
    """
    Main function for reporting bugs to Jira
    """
    def run_sql():
        '''
        Run sql cmdline and return the results
        :return: Tuple of the sql results
        '''
        new_teiid = teiid.Teiid()
        sql_tmpl = os.path.join(
            RESOURCE_PATH, 'psql', 'RHEL-libvirt-open-bugs-tmpl.sql')
        sql_file = os.path.join(
            RESOURCE_PATH, 'psql', 'RHEL-libvirt-open-bugs.sql')
        rep_dic = REPORT_MAP[params.version]
        with open(sql_tmpl, 'r') as sqltf:
            tem = sqltf.read()
            sqlcmd = tem % (rep_dic['product_id'],
                            rep_dic['component_id'],
                            params.arch,
                            rep_dic['product_id'],
                            rep_dic['component_id'],
                            params.arch,
                            rep_dic['rpl'],
                            )
            with open(sql_file, 'w') as sqlf:
                sqlf.write(sqlcmd)

        results = new_teiid.run_sql_file(sql_file)
        if len(results) == 3:
            oth_list = results[0]
            on_qa = results[1]
            rpl_list = results[2]
        else:
            raise Exception("Expect 3 SQL commands in file %s. Found %d." %
                            (sql_file, len(results)))
        return (oth_list, on_qa, rpl_list)

    def update_issue(jira_inst, project, parent, bug_list, rpl_list):
        """
        Check and create issues for new bugs in Jira
        """
        issue_dict = {
            'project': {
                'key': project,
            },
            'issuetype': {
                'name': 'Sub-task',
            },
            'assignee': {
                'name': REPORT_MAP[params.version][params.arch]['assignee'],
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
            issue_dict['labels'].append(params.arch)

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

    if params.version not in REPORT_MAP:
        raise Exception("Version %s is not supported" % params.version)
    else:
        if params.arch not in REPORT_MAP[params.version]:
            raise Exception("Arch %s is not supported" % params.arch)

    oth_list, on_qa, rpl_list = run_sql()
    jira_inst = jira.Jira()
    project = REPORT_MAP[params.version][params.arch]['project']

    rpl_list = [rpl_list[0][0], rpl_list[0][1].split(',')]

    parent = REPORT_MAP[params.version][params.arch]['onqa_parent']
    LOGGER.info("Check ON_QA bug issues under parent %s", parent)
    update_issue(jira_inst, project, parent, on_qa, rpl_list)

    parent = REPORT_MAP[params.version][params.arch]['other_parent']
    LOGGER.info("Check Other bug issues under parent %s", parent)
    update_issue(jira_inst, project, parent, oth_list, rpl_list)


def parse(parser):
    """
    Parse arguments for report bugs to jira
    """
    parser.add_argument(
        '--arch', dest='arch', action='store',
        default='ppc',
        help='The arch, support list: ppc, s390.')
    parser.add_argument(
        '--version', dest='version', action='store',
        default='RHEL-7.5',
        help='The version, support list: RHEL-7.4, RHEL-7.5.')
