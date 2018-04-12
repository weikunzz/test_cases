"""
Module to manage github related manipulations
"""
import time
import logging
import os
import re
import json
import tempfile
import urllib2

from libvirt_ci import utils

OAUTH_TOKEN = ("?client_id=b6578298435c3eaa1e3d&client_secret"
               "=59a1c828c6002ed4e8a9205486cf3fa86467a609")

GITHUB_API = "https://api.github.com"
GITHUB = "https://github.com"

LOGGER = logging.getLogger(__name__)


class PullRequest(object):
    def __init__(self, project, repo, pr_number):
        self._project = project
        self._repo = repo
        self._pr_no = pr_number
        self._url = ('%s/repos/%s/%s/pulls/%s' %
                     (GITHUB_API, self._project, self._repo, self._pr_no))
        self.refresh()

    def refresh(self, sleep=None, retry=None):
        retry = 20 if retry is None else retry
        sleep = sleep or 120
        try:
            self._data = urllib2.urlopen(self._url + OAUTH_TOKEN)
            self.data = json.load(self._data)
        except urllib2.HTTPError as error:
            LOGGER.error("Github refused our access with: %s", error.read())
            if retry:
                LOGGER.error("Sleep for %s seconds and try again, retry left %s",
                             sleep, retry)
                time.sleep(sleep)
                return self.refresh(sleep, retry - 1)
            else:
                raise

    def mergable(self):
        def _merge_compute_ready():
            self.refresh()
            return self.data['mergeable'] is not None

        if self.data['mergeable'] is None:
            utils.wait_for(_merge_compute_ready, 60)
        if self.data['mergeable'] is False:
            return False
        return not self.data['merged']

    def state(self):
        return self.data['state']

    def read(self, to_file=False):
        """
        Read the patch content of the PR
        """
        patch_url = self.data['patch_url']
        patch = urllib2.urlopen(patch_url).read()
        if not patch.strip():
            LOGGER.error('Empty content for PR #%s', self._pr_no)
            return
        if to_file:
            tmp_dir = tempfile.mkdtemp()
            patch_file = os.path.join(tmp_dir, "%s.patch" % self._pr_no)
            with open(patch_file, 'w') as patch_fp:
                patch_fp.write(patch)
            return patch_file
        return patch

    def change_files(self):
        """
        Get all change files of this pull requests
        """
        change_files = []
        change_files_url = self._url + '/files' + OAUTH_TOKEN
        change_files_data = json.load(urllib2.urlopen(change_files_url))
        for item in change_files_data:
            change_files.append(item['filename'])
        return change_files

    def comments(self):
        """
        Get all the comments of this pull request
        """
        comments_url = self.data['comments_url']
        return json.load(urllib2.urlopen(comments_url))

    def dependent_prs(self):
        """
        Get dependent pull requests from current pull requests description
        and comments
        """
        comments = self.data['body'].replace('\r\n', ' ')
        for comment in self.comments():
            comments += comment['body'].replace('\r\n', ' ')

        dependent_prs = []
        dependent_keywords = ['depends on']
        for keyword in dependent_keywords:
            pattern = r'%s %s/(\S+)/(\S+)/pull/(\d+)' % (keyword, GITHUB)
            LOGGER.info("Finding dependent PRs by '%s' in the comments")
            dependent_prs += re.findall(pattern, comments)
        return set(dependent_prs)
