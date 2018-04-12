"""
Class of jira service operation
"""
from __future__ import absolute_import

import logging
import requests
import jira

LOGGER = logging.getLogger(__name__)


class Jira(object):
    """
    jira operation class
    """
    __shared_state = {}

    def __init__(self, **args):
        """
        Init JIRA connection
        """
        requests.packages.urllib3.disable_warnings(
            requests.packages.urllib3.exceptions.InsecureRequestWarning)
        self.server = args.get(
            'server', 'https://projects.engineering.redhat.com')
        self.username = args.get('username', 'libvirt-jenkins')
        self.password = args.get('password', 'Redhat_Libvirt')
        self.verify = args.get('verify', False)
        self._jira = None
        self.authenticate()

    def authenticate(self):
        """
        Authenticate to the server
        """
        if 'jira' in self.__shared_state:
            self.jira_ = self.__shared_state['jira']
        else:
            options = {
                'server': self.server,
                'verify': self.verify,
            }
            basic_auth = (self.username, self.password)
            LOGGER.info("Connect to JIRA server %s", self.server)
            self.jira_ = jira.JIRA(options=options, basic_auth=basic_auth)
            self.__shared_state['jira'] = self.jira_

    def create_issue(self, issue_dict):
        """
        Create new issue
        """
        return self.jira_.create_issue(fields=issue_dict)

    def search_issues(self, project_name, jql_str, fields=None):
        """
        Search issue under the project and return result
        """
        jql_str = "project = " + project_name + " and " + jql_str
        LOGGER.info("The jql is: %s", jql_str)
        return self.jira_.search_issues(jql_str, maxResults=-1, fields=fields)

    def add_comment(self, issue, comment):
        """
        Add comments in the issue
        """
        self.jira_.add_comment(issue, comment)

    def transition_issue(self, issue, status):
        """
        Transition issue status to another
        """
        self.jira_.transition_issue(issue, status)

    def get_watchers(self, issue):
        """
        Get a watchers Resource from the server for an issue
        """
        watcher_data = self.jira_.watchers(issue)
        return [str(w.key) for w in watcher_data.watchers]

    def add_watcher(self, issue, watchers):
        """
        Append an issue's watchers list
        """
        new_watchers = []
        if isinstance(watchers, str):
            new_watchers.append(watchers)
        elif isinstance(watchers, list):
            new_watchers = watchers
        for watcher in new_watchers:
            self.jira_.add_watcher(issue, watcher)

    def remove_watcher(self, issue, watchers):
        """
        Remove watchers from an issue's watchers list
        """
        del_watchers = []
        if isinstance(watchers, str):
            del_watchers.append(watchers)
        elif isinstance(watchers, list):
            del_watchers = watchers
        for watcher in del_watchers:
            self.jira_.remove_watcher(issue, watcher)
