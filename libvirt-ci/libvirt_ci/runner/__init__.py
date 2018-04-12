"""
Module for the runner base class
"""
import logging
import collections
import ConfigParser
import fileinput
import glob
import os
import re
import shutil
import site
import subprocess
import sys
import tempfile
import time
import traceback
import urllib
import urllib2
import urlparse
import random
import yaml

import jenkins

from .. import abce
from .. import importer
from .. import package
from .. import report
from .. import state
from .. import utils
from .. import github

from libvirt_ci.data import RESOURCE_PATH, REPO_PATH, RUNTEST_PATH
from libvirt_ci.config import CONFIG_PATH

LOGGER = logging.getLogger(__name__)


class RunnerError(Exception):
    """
    Exception class for errors in Runner classes
    """
    pass


# pylint: disable=too-many-instance-attributes
class RunnerBase(object):
    """
    Base class for errors in Runner classes
    """
    __metaclass__ = abce.ABCEMeta
    defaults = {
        # Test framework, which runner to pick
        'test_framework': 'avocado-vt',
        # exclude some tests
        'no': '',
        # only include some tests
        'only': '',
        # report file
        'report': 'xunit_result.xml',
        # default password for ssh remote access
        'password': 'redhat',
        # default password for ssh remote access
        'pr': '',
        'patch': '',
        'chgs': '',
        'custom_repo': '',
        'yum_repos': '',
        'install_pkgs': '',
        'timeout': '1200',
        'net_name': 'default',
        'qemu_pkg': 'rhev',

        'list': False,
        'no_check': False,
        'no_recover': False,
        'fail_diff': False,
        'retain_vm': False,
        'update_all_pkgs': False,
        'smoke': False,
        'only_change': False,

        # Avocado-vt specific
        'vt_type': 'libvirt',
        'vm_type': '',
        'connect_uri': 'qemu:///system',
        'additional_vms': '',
        'slice': '',
        'config': '',
        'os_variant': 'fedora18',
    }

    __abstract_methods__ = []
    __abstract_properties__ = ['repos']

    default_nos = []
    error_pattern = r'(ERROR)(\s+)(.*)$'
    result_line_pattern = r'(ERROR)(\s+)(.*)$'
    required_packages = []
    main_vm = None
    working_dir = None

    def __init__(self, name, env, params):
        self.name = name
        self.env = env
        self.nos = None
        self.onlys = None
        self.states = None
        self.report = None
        self.tests = None
        self.coverage = None
        self.libvirt_pkg = None
        self.qemu_kvm_pkg = None
        self.qemu_kvm = 'rhev'

        self.params = params
        if self.params.test_path:
            self.test_path = self.params.test_path
        else:
            self.params.test_path = self.test_path = os.path.join(
                RUNTEST_PATH, self.params.test_framework)
        if self.params.host:
            self.host = self.params.host
        else:
            self.host = None
        self.load_default_values()
        self.load_custom_repos()
        self.cur_test_idx = None
        self.host_arch = utils.get_arch(host=self.host)
        (self.dist_name, self.dist_major,
         self.dist_minor,
         self.dist_codename) = utils.get_dist(host=self.host)
        self.ignore_failures = collections.defaultdict(list)

        self.init()
        if self.params.enable_coverage:
            self.init_coverage()

    def load_default_values(self):
        for key, value in self.defaults.items():
            self.params.setdefault(key, value)

    # pylint: disable=no-member
    def load_custom_repos(self):
        """
        Update git repo info if custom repo info specified
        """
        for line in self.params.custom_repo.splitlines():
            repo, url_branch_commit = line.split(None, 1)
            self.repos[repo] = url_branch_commit

    def init(self):
        """
        Default method for test framework specific initialization.
        """
        pass

    def replace(self):
        """
        Default method for test framework specific replacements.
        """
        pass

    def bootstrap(self):
        """
        Default method for test framework specific bootstrap.
        """
        pass

    def init_framework_params(self):
        """
        Default method for test framework specific parameter initialization.
        """
        pass

    # pylint: disable=no-self-use
    def list_tests(self):
        """
        Default method for test framework specific test list.
        """
        return []

    def custom_prepare(self):
        """
        Default method for test framework specific preparation.
        """
        pass

    def prepare_test(self, test_name):
        """
        Default method for test framework specific test case preparation.
        """
        pass

    def prepare_run(self):
        """
        Default method for run specific preparation.
        """
        self.init_params()
        utils.restart_service('libvirtd')
        if ((self.dist_major == 7 and self.dist_name == 'redhat') or
                (self.dist_major >= 22 and self.dist_name == 'fedora')):
            utils.run('systemctl start virtlogd.socket')

    def run_test(self, test_name):
        """
        Default method for test framework specific test run.
        """
        pass

    def parse_result(self, result):
        """
        Default method for test framework specific test result parse.
        """
        pass

    def check_need_rerun(self, _result):
        """
        Default method for test framework specific checking if one test need
        rerun
        """
        return False, None

    def init_coverage(self):
        """
        Default method for test framework prepare coverage
        """
        LOGGER.warning('Ignoring enable undefined coverage helper')

    def update_report(self, test, status, result_line, duration, logs,
                      _idx):
        """
        Default method for test framework specific test result parse.
        """
        class_name, test_name = test.split('.', 1)
        status, result_line = self._ignore_failures(
            test_name, status, result_line)
        self.report.update(test_name, class_name, status, '\n'.join(logs),
                           result_line, duration,
                           prefix=self.params.qemu_pkg)

    def filter_tests(self, pattern):
        """
        Filter a list of test names by a matching pattern.
        """
        filtered_tests = []
        for test in self.tests:
            if utils.test_match(pattern, test):
                filtered_tests.append(test)
        return filtered_tests

    def prepare_tests(self, filter_tests=True):
        """
        Get all tests to be run.
        """
        def _filter_tests(tests, verbose=True):
            """
            Filter tests according to onlys and nos.
            """
            def _filter_by_blacklist(tests, verbose=True):
                type_keys_map = {
                    'not-supported': ['feature'],
                    'not-in-plan': ['reason'],
                    'bug-wont-fix': ['bug'],
                    'bug-not-fixed': ['bug'],
                    'case-updating': ['task'],
                    'hazardous-case': ['reason'],
                    'need-env': ['env'],
                }
                blacklist_path = os.path.join(CONFIG_PATH, 'blacklist.yaml')

                with open(blacklist_path) as blacklist_fp:
                    blacklists = yaml.load(blacklist_fp)

                blacklist = {}
                for blacklist_type in type_keys_map:
                    blacklist[blacklist_type] = []

                for scenario in blacklists:
                    # Prepare variables for eval
                    # pylint: disable=unused-variable,eval-used
                    params = self.params  # noqa
                    info = self  # noqa
                    # If 'when' don't exists, it means the blacklist applies
                    # for any condition
                    any_package = package.any_package
                    if 'when' not in scenario or eval(scenario['when']):
                        for blacklist_type, entries in scenario.items():
                            if blacklist_type in ['when', 'description']:
                                continue

                            for entry in entries:
                                entry['scenario'] = scenario['description']
                            blacklist[blacklist_type].extend(
                                scenario[blacklist_type])

                blacked_tests = set()
                for blacklist_type, entries in blacklist.items():
                    for entry in entries:
                        if blacklist_type == 'not-supported':
                            reason = ("Feature '%s' is not supported %s" %
                                      (entry['feature'], entry['scenario']))
                        elif blacklist_type == 'not-in-plan':
                            reason = ("Case is not in test plan %s because "
                                      "%s" % (entry['scenario'],
                                              entry['reason']))
                        elif blacklist_type == 'bug-wont-fix':
                            reason = ("Bug '%s' won't be fixed %s" %
                                      (entry['bug'], entry['scenario']))
                        elif blacklist_type == 'bug-not-fixed':
                            reason = ("Bug '%s' is not fixed yet %s" %
                                      (entry['bug'], entry['scenario']))
                        elif blacklist_type == 'case-updating':
                            reason = ("Case is updating %s: https://projects."
                                      "engineering.redhat.com/browse/%s" %
                                      (entry['scenario'], entry['task']))
                        elif blacklist_type == 'hazardous-case':
                            reason = ("Case is hazardous %s: %s" %
                                      (entry['scenario'], entry['reason']))
                        elif blacklist_type == 'need-env':
                            reason = ("Case require env '%s' to run %s" %
                                      (entry['env'], entry['scenario']))
                        else:
                            raise Exception("Unknown blacklist type %s" %
                                            blacklist_type)

                        patterns = entry['test']
                        if isinstance(patterns, (str, unicode)):
                            patterns = [patterns]
                        elif not isinstance(patterns, (list, tuple)):
                            raise Exception('Unknown test type %s for %s' %
                                            type(patterns), entry)

                        blacked = []
                        for test in tests:
                            if any(utils.test_match(patt, test)
                                   for patt in patterns):
                                blacked.append(test)

                        if 'skip-test' in entry and not entry['skip-test']:
                            for test in blacked:
                                self.ignore_failures[test].append({
                                    'fail-regex': entry['fail-regex'],
                                    'reason': reason,
                                })
                            continue
                        else:
                            for test in blacked:
                                self.update_report(test, "SKIP", "[BLACKLISTED] %s" % reason,
                                                   0, [], None)

                        if blacked:
                            LOGGER.info('%d tests blacked because "%s"',
                                        len(blacked), reason)
                            if verbose:
                                for test in blacked:
                                    LOGGER.info('\t%s', test)
                        blacked_tests.update(blacked)

                filtered_tests = []
                for test in tests:
                    if test not in blacked_tests:
                        filtered_tests.append(test)

                return filtered_tests

            LOGGER.info('Found %s cases', len(tests))
            if self.onlys:
                LOGGER.info("Filtering with only:")
                for only in self.onlys:
                    LOGGER.info("\t%s", only)
            if self.nos:
                LOGGER.info("Filtering with no:")
                for no_ in self.nos:
                    LOGGER.info("\t%s", no_)

            filtered_tests = []
            for test in tests:
                if self.onlys is not None:
                    if all(not utils.test_match(only, test)
                           for only in self.onlys):
                        continue
                if self.nos is not None:
                    if any(utils.test_match(no, test)
                           for no in self.nos):
                        continue
                filtered_tests.append(test)
            LOGGER.info('Filtered to %s cases', len(filtered_tests))

            tests = filtered_tests
            filtered_tests = _filter_by_blacklist(tests, verbose)
            LOGGER.info('Filtered to %s cases by blacklist',
                        len(filtered_tests))

            return filtered_tests

        def get_tests(filter_tests=True, verbose=True):
            """
            Get all virt tests.
            """
            if self.onlys is not None and not self.onlys:
                return []

            tests = self.list_tests()
            if filter_tests:
                tests = _filter_tests(tests, verbose)
            return tests

        def get_tests_for_only_change(filter_tests=True, additional_cases_num=5):
            """
            Get the new introduced cases by the change, and pickup additional
            number cases from the left cases in case no new case introduced.
            """
            new_cases = set()
            cases_with_change = get_tests(filter_tests=filter_tests,
                                          verbose=False)
            changed_repo = {}
            for param in self.params:
                if param.endswith('_current_branch') and 'avocado' not in param:
                    changed_repo[param[:-15]] = self.params[param]
            for repo in changed_repo:
                # Assume master branch has no change
                self._checkout_to_branch(repo, 'master')
            self.bootstrap()
            cases_without_change = get_tests(filter_tests=filter_tests,
                                             verbose=False)
            for repo in changed_repo:
                self._checkout_to_branch(repo, changed_repo[repo])
            self.bootstrap()

            new_cases = set(cases_with_change) - set(cases_without_change)
            LOGGER.info("%s new cases introduced by change:\n%s", len(new_cases),
                        str(new_cases))

            left_cases = set(cases_with_change) - new_cases
            if len(left_cases) < additional_cases_num:
                additional_cases_num = len(left_cases)
            additional_cases = set(random.sample(left_cases,
                                                 additional_cases_num))
            LOGGER.info("%s additional cases for only-change testing:\n%s",
                        len(additional_cases), str(additional_cases))

            return new_cases | additional_cases

        def change_to_only(change_files):
            """
            Transform change files to a only set
            """
            name_patt = ('%s/tests/(cfg|src)/(.*).(cfg|py)' %
                         self.params.vt_type)
            onlys = set()
            for chg_file in change_files:
                res = re.match(name_patt, chg_file)
                if res:
                    cfg_path = '%s/tests/cfg/%s.cfg' % (self.params.vt_type,
                                                        res.groups()[1])
                    LOGGER.info("Current test configuration: %s", cfg_path)
                    cfg_path = os.path.join(self.params.tp_libvirt_dir,
                                            cfg_path)
                    try:
                        with open(cfg_path) as fcfg:
                            only = fcfg.readline().strip()
                            only = only.lstrip('-').rstrip(':').strip()
                            onlys.add(only)
                    # pylint: disable=broad-except
                    except Exception as details:
                        LOGGER.warning('Ignoring exception: %s', details)
            return onlys

        self.nos = set(self.default_nos)
        self.onlys = None

        if self.params.only:
            self.onlys = set(utils.split(self.params.only))

        if self.params.slice:
            slices = {}
            slice_opts = utils.split(self.params.slice)
            slice_url = slice_opts[0]
            slice_opts = slice_opts[1:]
            config = urllib2.urlopen(slice_url)
            for line in config:
                key, val = line.split()
                slices[key] = val
            for slice_opt in slice_opts:
                if slice_opt in slices:
                    if self.onlys is None:
                        self.onlys = set(slices[slice_opt].split(','))
                    else:
                        self.onlys |= set(slices[slice_opt].split(','))
                elif slice_opt == 'other':
                    for key in slices:
                        self.nos |= set(slices[key].split(','))

        if self.params.no:
            self.nos |= set(utils.split(self.params.no))
        if self.params.only_change:
            change_files = self.params.get('change_files', [])
            if self.onlys is not None:
                self.onlys &= change_to_only(change_files)
            else:
                self.onlys = change_to_only(change_files)
            tests = get_tests_for_only_change(filter_tests=filter_tests)
        else:
            tests = get_tests(filter_tests=filter_tests)

        with open('run.test', 'w') as tests_fp:
            for test in tests:
                tests_fp.write(test + '\n')

        if self.params.list:
            for test in tests:
                print test
            exit(0)

        self.tests = tests

        if not self.tests:
            self.report.update("", "no_test.no_test", "NOTESTS", "", "", 0)
            raise RunnerError("No test to run")

    def run_a_test(self, test):
        """
        Run a specific test.
        """
        result = self.run_test(test)
        status = 'INVALID'
        status, logs = self.parse_result(result)

        if result.exit_status == 'timeout':
            status = 'TIMEOUT'

        if status == 'INVALID' and result.exit_code:
            LOGGER.error("Unexpected test result:\n%s", result)

        color = {
            'HEADER': '\033[35m',
            'PASS': '\033[32m',
            'SKIP': '\033[33m',
            'WARN': '\033[33m',
            'ERROR': '\033[31m',
            'FAIL': '\033[31m',
            'TIMEOUT': '\033[31m',
            'INVALID': '\033[31m',
            'BOLD': '\033[1m',
            'UNDERLINE': '\033[4m',
        }
        status_color = color['ERROR']
        if status in color:
            status_color = color[status]
        utils.output('Result: \033[1m%s%s\033[0m %.2f s\n' %
                     (status_color, status, result.duration))

        # Get result line
        result_line = ''
        for line in logs:
            matches = re.findall(self.result_line_pattern, line)
            if matches:
                match_text = matches[0][2]
                if match_text.startswith('-> '):
                    match_text = match_text[3:]
                result_line += utils.escape(match_text + '\n')

        test_result = {
            'test': test,
            'status': status,
            'logs': logs,
            'result_line': result_line,
            'duration': result.duration,
            'test_index': self.cur_test_idx,
        }
        return test_result

    def process_result(self, result):
        """
        Save a test result and log problems
        """
        test = result['test']
        status = result['status']
        result_line = result['result_line']
        duration = result['duration']
        logs = result['logs']
        test_index = result['test_index']

        self.update_report(test, status, result_line, duration, logs,
                           test_index)
        self.report.save(self.params.report)

        # Get and print error messages
        err_msg = []
        if status == 'INVALID':
            err_msg = logs
            return

        for line in logs:
            if re.match(self.error_pattern, line):
                err_msg.append(line)

        if not self.params.no_check:
            diff_msg = self.states.check(
                recover=(not self.params.no_recover))
            if diff_msg:
                diff_msg = ['   DIFF|%s' % l for l in diff_msg]
                err_msg = diff_msg + err_msg

        if err_msg:
            for line in err_msg:
                LOGGER.info(line)

    # pylint: disable=no-member
    def prepare_git_repos(self, clean_only=False):
        """
        Prepare test required git repos
        """
        if not clean_only:
            # Download git repos/Update existing git repos
            for repo_name, repo_line in self.repos.items():
                repo_url, branch, commit = utils.split_repo_line(repo_line)
                utils.update_git_repo(repo_name, repo_url, branch, commit)

        # Make/Clear up test path
        test_path = self.test_path
        if os.path.exists(test_path):
            LOGGER.info("Testing path %s already exists. Clearing", test_path)
            shutil.rmtree(test_path)
        os.mkdir(test_path)

        # Copy git repos into temporary test path
        for repo in self.repos:
            repo_dir = os.path.join(REPO_PATH, repo)
            LOGGER.info("Copying '%s' to %s", repo_dir, test_path)
            shutil.copytree(repo_dir, os.path.join(test_path, repo),
                            symlinks=True)

            old_path = os.getcwd()
            try:
                os.chdir(os.path.join(self.test_path, repo))
                res = utils.run('git reset')  # Fix rare git problem
                if res.exit_code:
                    LOGGER.error('Failed to perform "git reset", %s', res)
            finally:
                os.chdir(old_path)

    def _checkout_to_branch(self, repo_name, branch_name):
        """
        Create(if not exist) and checkout to a branch
        """
        # TODO: Could be moved to a standalone module for git repo management
        old_path = os.getcwd()
        try:
            os.chdir(os.path.join(self.test_path, repo_name))
            LOGGER.info("Checkout to branch: %s", branch_name)
            cmd = 'git checkout %s %s'
            option = ''
            if branch_name not in utils.run('git branch').stdout:
                option = '-b'
            ret = utils.run(cmd % (option, branch_name))
            if ret.exit_code:
                LOGGER.error("Checkout to branch failed: %s", ret)
                return False
            # Update repo branch to params
            repo_branch = "%s_current_branch" % repo_name
            self.params[repo_branch] = branch_name
        finally:
            os.chdir(old_path)
        return True

    # pylint: disable=no-member
    def prepare_a_pr(self, repo_name, pull_no):
        """
        Merge pull request of a repo
        """
        old_path = os.getcwd()
        try:
            os.chdir(os.path.join(self.test_path, repo_name))
            url = self.repos[repo_name].split()[0]
            prj_name, repo_name = re.split(
                r"^.*github.com[/:]([^/]+)/([^/]+).git", url)[1:3]
            pr = github.PullRequest(prj_name, repo_name, pull_no)

            if pr.mergable():
                patch_file = pr.read(to_file=True)
                if not patch_file:
                    return True

                new_branch = "patch_pr%s" % pull_no
                if not self._checkout_to_branch(repo_name, new_branch):
                    return False

                LOGGER.info('Patching %s PR #%s', repo_name, pull_no)
                cmd = 'git am -3 %s' % patch_file
                res = utils.run(cmd)
                if res.exit_code:
                    LOGGER.error('Failed applying PR %s: %s', pull_no, res)
                    return False
                os.remove(patch_file)
                # Append change files of this pr
                if not self.params.change_files:
                    self.params.change_files = []
                self.params.change_files += pr.change_files()
            else:
                LOGGER.error('PR %s is not mergable', pull_no)
        except Exception as error:
            LOGGER.error('Failed applying PR %s with exception %s', pull_no, error)
            raise
        finally:
            os.chdir(old_path)
        LOGGER.info('Processed PR %s: %s', repo_name, pull_no)
        return True

    def prepare_a_patch(self, repo_name, patch):
        """
        Merge patch on current work dir repo

        param patch: path could be absolute path or relative path base on
        current work dir
        """

        def _get_patch_path(patch):
            LOGGER.debug('Getting path for patch "%s"', patch)
            parse_result = urlparse.urlparse(patch)
            if (parse_result.scheme in ['file', ''] and
                    not parse_result.netloc):
                LOGGER.debug('It is a local patch')
                if os.path.isfile(patch):
                    return patch
                else:
                    patch_file = os.path.join(RESOURCE_PATH, 'patch', patch)
                    if os.path.isfile(patch_file):
                        return patch_file
                    else:
                        LOGGER.error('Patch file %s not exists', patch)
            else:
                LOGGER.debug('It is a remote patch')
                patch_file = tempfile.NamedTemporaryFile(
                    mode='w', suffix='.patch', prefix='libvirt-ci-',
                    delete=False)
                try:
                    patch_file.write(urllib2.urlopen(patch).read())
                except urllib2.URLError as detail:
                    LOGGER.error('Patch not reachable: %s', detail.args)
                finally:
                    patch_file.close()
                with open(patch_file.name, 'r') as patch_fp:
                    if not patch_fp.read().strip():
                        LOGGER.warning('Empty content for patch: %s',
                                       patch)
                return patch_file.name

        old_path = os.getcwd()
        try:
            os.chdir(os.path.join(self.test_path, repo_name))
            patch_file = _get_patch_path(patch)
            if os.path.isfile(patch_file):
                new_branch = "patch_%s" % os.path.basename(patch_file)
                if not self._checkout_to_branch(repo_name, new_branch):
                    return False

                cmd = "git am -3 %s" % patch_file
                res = utils.run(cmd)
                if res.exit_code:
                    LOGGER.error("Failed to apply patch %s with git\n%s",
                                 patch_file, res.stderr)
                    cmd = "patch -p1 < %s" % patch_file
                    res = utils.run(cmd)
                    if res.exit_code:
                        LOGGER.error(
                            "Failed to apply patch %s with patch, ignore "
                            "the patch file.:\n%s", patch_file, res.stderr)
            else:
                LOGGER.warning("Skip patch %s as only file is supported", patch_file)
        finally:
            os.chdir(old_path)
        LOGGER.info("Patched '%s' with file '%s'", repo_name, patch_file)
        return True

    def prepare_a_change(self, repo_name, chg_id):
        """
        Cherry pick a change on current repo
        """
        fetch_url = ("http://git.host.prod.eng.bos.redhat.com/git/%s.git"
                     % repo_name)
        old_path = os.getcwd()
        try:
            os.chdir(os.path.join(self.test_path, repo_name))
            new_branch = "patch_%s" % os.path.basename(chg_id)
            if not self._checkout_to_branch(repo_name, new_branch):
                return False

            cmd = ("git checkout;git fetch %s %s && git cherry-pick "
                   "--ff FETCH_HEAD" % (fetch_url, chg_id))
            res = utils.run(cmd)
            LOGGER.info(res)
            if res.exit_code:
                LOGGER.warning("Failed to cherry-pick %s", chg_id)
                # Try to revert if any error
                utils.run("git cherry-pick --abort")
                return False
        finally:
            os.chdir(old_path)
        LOGGER.info("Cherry-pick '%s' change '%s'", repo_name, chg_id)
        return True

    def replace_pattern_in_file(self, file_path, search_exp, replace_exp,
                                repo=None):
        """
        Replace a specific regex pattern with a replacement in specified file
        """
        if repo is not None:
            path = os.path.join(self.test_path, repo, file_path)
        else:
            path = file_path

        file_names = glob.glob(path)
        if not file_names:
            raise OSError("Can't find file '%s' for replacement" % path)

        prog = re.compile(search_exp)
        for file_name in file_names:
            for idx, line in enumerate(fileinput.input(file_name, inplace=1)):
                match = prog.search(line)
                if match:
                    LOGGER.info("Replacing %s: line %d", file_name, idx)
                    LOGGER.info("\tRegex: %s", search_exp)
                    LOGGER.info("\tFrom : %s", line.strip())
                    line = prog.sub(replace_exp, line)
                    LOGGER.info("\tTo   : %s", line.strip())
                sys.stdout.write(line)

    def prepare_replaces(self):
        def _repl(match):
            env = match.groups()[1]
            if env.upper() in os.environ:
                return os.environ[env.upper()]
            elif env in os.environ:
                return os.environ[env]
            else:
                LOGGER.warning('Env %s not found while replacing', env)
                return ''

        # Apply test framework specific replacements
        self.replace()

        # Return directly if no replacement specified
        if not self.params.replaces:
            return

        cur_files = []
        cur_repo = None
        for line in self.params.replaces.splitlines():
            line = line.strip()
            if '-->' in line:
                if not cur_files:
                    raise ValueError(
                        "Expect starts with file name ends with ':', "
                        "but got:\n%s" % line)
                s_from, s_to = line.split('-->', 1)
                if ((s_from.strip().startswith('"') and
                     s_from.strip().endswith('"')) or
                        (s_from.startswith("'") and
                         s_from.endswith("'"))):
                    s_from = s_from.strip()[1:-1]
                if ((s_to.strip().startswith('"') and
                     s_to.strip().endswith('"')) or
                        (s_to.startswith("'") and
                         s_to.endswith("'"))):
                    s_to = s_to.strip()[1:-1]

                # Replace placeholders '{{env_name}}' to environment content
                s_from = re.sub('({{)(.*?)(}})', _repl, s_from)
                s_to = re.sub('({{)(.*?)(}})', _repl, s_to)

                for cur_file in cur_files:
                    if os.path.isfile(cur_file):
                        self.replace_pattern_in_file(cur_file, s_from, s_to)
            elif line.endswith(':'):
                if ' ' in line:
                    cur_repo, line = line.split(None, 1)
                else:
                    cur_repo = None

                paths = utils.split(line[:-1])
                if cur_repo:
                    paths = [
                        os.path.join(self.test_path, cur_repo, path)
                        for path in paths]
                # Flatten all paths to a list
                cur_files = sum([glob.glob(path) for path in paths], [])
                if not cur_files:
                    raise ValueError(
                        "Expect a existing file name, "
                        "but got:\n%s" % line)
            elif line.strip().startswith('#'):
                pass
            else:
                raise ValueError(
                    "Expect '-->' in line or line ends with ':', "
                    "but got:\n%s" % line)

    def prepare_packages(self):
        if self.params.yum_repos:
            repos = utils.split(self.params.yum_repos)
            repo_dict = {}
            for repo_str in repos:
                if repo_str:
                    if '|' in repo_str:
                        repo_name, repo_url = repo_str.split('|')
                    else:
                        repo_name = repo_str
                        repo_url = None
                    repo_dict[repo_name] = repo_url
            self.env.setup_repos(repo_dict)

        utils.run('yum clean all')

        if self.params.update_all_pkgs:
            self.env.update_pkgs()

        self.env.replace_qemu_rhev(self.params.qemu_pkg, arch=self.host_arch)
        resource = os.environ.get('RESOURCE_HOSTNAME')
        if resource:  # For migration / job with a resource machine
            self.env.replace_qemu_rhev(self.params.qemu_pkg, host=resource, arch=self.host_arch)
            self.prepare_services(host=resource)

        pkgs = utils.split(self.params.install_pkgs) + self.required_packages
        if pkgs:
            self.env.install_pkgs(pkgs)

    def prepare_services(self, host=None):
        common_services = ['libvirtd', 'nfs', 'iscsid']
        pre_rhel6_services = ['cgconfig', 'tgtd', 'rpcbind']
        post_rhel7_services = ['virtlogd.socket']
        if self.dist_major == 6 and self.dist_name == 'redhat':
            utils.restart_service(pre_rhel6_services, host=host)
        utils.restart_service(common_services, host=host)
        if ((self.dist_major == 7 and self.dist_name == 'redhat') or
                (self.dist_major >= 22 and self.dist_name == 'fedora')):
            utils.restart_service(post_rhel7_services, host=host)

    def prepare_selinux(self):
        mod_name = 'libvirt_ci'
        se_rule = None

        if self.dist_name == 'redhat' and self.dist_major == 6:
            se_rule = 'rhel6.te'
        elif ((self.dist_name == 'redhat' and
               self.dist_major == 7) or
              (self.dist_name == 'fedora' and
               self.dist_major >= 23)):
            se_rule = 'rhel7.te'
        else:
            LOGGER.error("Libvirt-ci don't have selinux rule prepared for"
                         "this distribution (%s, %s)", self.dist_name, self.dist_major)
            return

        res = utils.run("semodule -l", host=self.host)
        if mod_name in res.stdout:
            LOGGER.info("SELinux module %s already exists. Skip setup",
                        mod_name)
            return

        LOGGER.info("Setting up SELinux module %s", mod_name)

        mod_path = '/tmp/%s.te' % mod_name
        se_rule_file = os.path.join(RESOURCE_PATH, 'selinux', se_rule)
        shutil.copy(se_rule_file, mod_path)
        if self.host:
            utils.run_playbook('copy_file',
                               hosts=self.host,
                               private_key='libvirt-jenkins',
                               ignore_fail=True,
                               remote=self.host,
                               file_path=mod_path)

        utils.run("checkmodule -M -m -o /tmp/%s.mod /tmp/%s.te" %
                  (mod_name, mod_name), host=self.host)
        utils.run("semodule_package -o /tmp/%s.pp -m /tmp/%s.mod" %
                  (mod_name, mod_name), host=self.host)
        utils.run("semodule -i /tmp/%s.pp" % mod_name, host=self.host)

    def init_params(self):
        self.libvirt_pkg = package.Package.from_name('libvirt',
                                                     host=self.host)
        try:
            self.qemu_kvm_pkg = package.Package.from_name('qemu-kvm',
                                                          host=self.host)
            self.qemu_kvm = 'rhel'
        except package.PackageError:
            try:
                self.qemu_kvm_pkg = package.Package.from_name('qemu-kvm-rhev',
                                                              host=self.host)
                self.qemu_kvm = 'rhev'
            except package.PackageError:
                self.qemu_kvm_pkg = package.Package.from_name('qemu-kvm-ma',
                                                              host=self.host)
                self.qemu_kvm = 'rhel'
        self.init_framework_params()

    def prepare_framework(self):
        self.prepare_replaces()
        self.bootstrap()

        # Reload all packages to ensure new packages just installed is loaded
        reload(site)

        self.init_params()
        # Prepare image must follow init_params since it requires img_path
        self.prepare_image()

    def backup_image(self):
        """
        Backup image file by copying
        """
        image_path = self.params.img_path
        backup_image_path = self.params.img_path + '.backup'
        LOGGER.info('Backing up image from %s to %s',
                    image_path, backup_image_path)
        shutil.copyfile(image_path, backup_image_path)

    def restore_image(self):
        """
        Restore image file by copying
        """
        image_path = self.params.img_path
        backup_image_path = self.params.img_path + '.backup'
        LOGGER.info('Restoring image from %s to %s',
                    backup_image_path, image_path)
        shutil.copyfile(backup_image_path, image_path)

    def prepare_image(self):
        if (self.params.img_url and
                hasattr(self.params, 'img_path') and
                self.params.img_path):
            LOGGER.info('Downloading image from %s to %s',
                        self.params.img_url, self.params.img_path)
            urllib.urlretrieve(self.params.img_url, self.params.img_path)
            self.backup_image()

    def prepare_state(self):
        self.states = state.States(host=self.host)
        self.states.backup()

    def prepare_test_objects(self):
        if not self.params.test_objects:
            return

        for test_object_str in self.params.test_objects.splitlines():
            test_object = dict([item.split(':', 1)
                                for item in test_object_str.split()])
            source = test_object["source"]
            params = self.params.copy()
            params.update(test_object)

            playbook_path = os.path.join(
                RESOURCE_PATH, 'playbooks', 'roles',
                'test_object_sources', source + '.yaml')
            if os.path.isfile(playbook_path):
                utils.run_playbook(playbook_path, debug=True,
                                   **params)
            else:
                LOGGER.warning("Can't locate playbook to setup test object "
                               "'%s' with source '%s'. Skipping test object "
                               "preparation", test_object, source)

    def prepare_report(self):
        """
        Call this method only after all package and env is ready
        Report module will record current env as the testing env.
        """
        show_pkgs = utils.split(self.params.show_packages)
        label_pkgs = utils.split(self.params.label_package)
        install_pkgs = utils.split(self.params.install_pkgs) + self.required_packages

        self.report = report.Report(fail_diff=self.params.fail_diff,
                                    host=self.host)
        self.report.record_params(self.params)
        self.report.record_ci_message(self.params.message)
        self.report.record_env()
        self.report.record_packages(show_pkgs + label_pkgs or install_pkgs)
        self.report.record_report_keys()

    def prepare_env(self):
        self.prepare_services()
        self.prepare_selinux()

    def _ignore_failures(self, test_name, result, result_msg):
        """
        Change failed test result to SKIP if pattern matched
        """
        for tname in self.ignore_failures:
            if test_name not in tname:
                continue

            found_match = False
            match_msg = ""
            for issue in self.ignore_failures[tname]:
                fail_regexes = issue['fail-regex']
                reason = issue['reason']
                for regex in fail_regexes:
                    if re.findall(regex, result_msg):
                        found_match = True
                        match_msg += ('Match: "%s" Reason: "%s"' %
                                      (regex, reason))
            if found_match:
                result = 'SKIP'
                result_msg += 'Test failure ignored. (%s)' % match_msg
        return result, result_msg

    def run(self, max_rerun=3):
        """
        Run continuous integrate for virt-test test cases.
        """
        self.prepare_run()
        self.prepare_report()
        self.prepare_tests()
        self.prepare_state()

        if self.coverage:
            try:
                self.coverage.prepare()
            # pylint: disable=broad-except
            except Exception as detail:
                LOGGER.warning('Cannot prepare coverage env: %s, disable coverage driver', detail)
                self.coverage = None

        try:
            for idx, test in enumerate(self.tests):
                self.cur_test_idx = idx
                self.prepare_test(test)

                utils.output('%s (%d/%d) %s ' % (time.strftime('%X'), idx + 1,
                                                 len(self.tests), test))

                rerun = 0
                while True:
                    test_result = self.run_a_test(test)
                    need_rerun, reason = self.check_need_rerun(test_result)
                    if not need_rerun:
                        break
                    rerun += 1
                    if rerun == max_rerun:
                        LOGGER.error('Test still fail after %d rerun: %s',
                                     rerun, reason)
                        break
                    else:
                        LOGGER.error('Need to rerun this test since: %s',
                                     reason)
                self.process_result(test_result)

        # pylint: disable=broad-except
        except Exception:
            traceback.print_exc()
        finally:
            self.report.save(self.params.report)

        if self.coverage:
            try:
                self.coverage.gen_report()
            # pylint: disable=broad-except
            except Exception as detail:
                LOGGER.warning('Fail to create coverage report: %s', detail)

        # Return fail/error case count
        fail_count = 0
        for status_type in ['FAIL', 'ERROR', 'TIMEOUT', 'INVALID']:
            fail_count += self.report.result_counter.get(status_type, 0)
        return fail_count


def _process_params(params):
    """
    Override test parameters if it exists in env.
    """
    def _save_params(build_params, param_file):
        config = ConfigParser.ConfigParser()
        config.optionxform = str
        for param in build_params:
            config.set('DEFAULT', param['name'], param['value'])
        # Reset several parameters require Jenkins specific environ
        config.set('DEFAULT', 'CI_TEST_PATH', '')
        config.set('DEFAULT', 'CI_REPORT', '')
        config.set('DEFAULT', 'CI_TEXT_REPORT', '')
        config.write(param_file)

    def _load_params(param_path):
        config = ConfigParser.ConfigParser()
        config.optionxform = str
        config.read(param_path)
        for name, value in config.items('DEFAULT'):
            print name, value
            os.environ[name] = value

    def _process_rerun():
        # Parse Jenkins URL
        url = params.rerun
        match = re.findall(
            r'(https?://[^/]+).*/job/([^/]+)/([^/]+)/', url)
        if not match:
            raise RunnerError("Can't parse Jenkins URL %s" % url)

        # Get build parameters from Jenkins
        server_url, job, build_number = match[0]
        server = jenkins.Jenkins(server_url)
        build_info = server.get_build_info(job, int(build_number))
        build_params = {}
        for entry in build_info['actions']:
            if 'parameters' in entry:
                build_params = entry['parameters']
        if not build_params:
            LOGGER.warning('No parameters found in Jenkins build %s', url)

        # Create a temporary config file to save parameters
        param_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.cfg', prefix='libvirt_ci_rerun_',
            delete=False)
        _save_params(build_params, param_file)
        param_file.close()

        # Allow user to edit this file
        edit_file = utils.query_yes_no(
            "Edit parameter file?", default="no")
        if edit_file:
            editor = os.getenv('EDITOR', 'vi')
            subprocess.call('%s %s' % (editor, param_file.name),
                            shell=True)

        # Apply parameter files to environ
        _load_params(param_file.name)

        # Remove temporary parameter file
        if os.path.exists(param_file.name):
            try:
                os.remove(param_file.name)
            except (IOError, OSError):
                LOGGER.warning('Can not remove temp file %s',
                               param_file.name)

    params_dict = {}
    if hasattr(params, 'rerun') and params.rerun:
        _process_rerun()

    # Get parameters from environment variables
    for key, value in os.environ.items():
        if key.startswith('CI_'):
            params_dict[key[3:].lower()] = value

    # Get parameters from command line arguments
    for key, value in params_dict.items():
        if value and hasattr(params, key):
            old_value = getattr(params, key)
            if isinstance(old_value, bool):
                if str(value).lower() == 'true':
                    new_value = True
                else:
                    new_value = False
            else:
                new_value = value

            if new_value != old_value:
                LOGGER.info(
                    "Replacing parameter '%s' with env ('%s'->'%s')",
                    key, old_value, new_value)
                setattr(params, key, new_value)

    LOGGER.info("Test parameters:")
    for key, value in params.items():
        LOGGER.info("%-30s %s", key, value)


def get_runner(env, params):
    """
    Get corresponding test runner instance according to
    test-framework parameter.
    """
    _process_params(params)
    framework = params.test_framework
    module_name = framework.replace('-', '_')
    class_name = ''.join(
        module_name.replace('_', ' ').title().split())
    if params.host and 'avocado' in module_name:
        class_name += 'Remote'
    class_name += 'Runner'

    runner_mod = importer.import_module('libvirt_ci.runner.' + module_name)
    cls = getattr(runner_mod, class_name)
    return cls(framework, env, params)
