#!/usr/bin/env python
"""
List all auto test case, and upload to caselink.
"""
import logging
import os
import requests

from .. import config
from .. import env
from .. import utils
from .. import github

from libvirt_ci.params import Parameters
from libvirt_ci.jenkins_job import JobGenerator

LOGGER = logging.getLogger(__name__)

UPDATE_KEYS = ['framework', 'components']
# TODO: use a standlone module to manage pr/repos
GITHUB_REPOS = {
    'tp-libvirt': {
        'project': 'autotest',
        'repo': 'tp-libvirt'
    }
}


def get_tests_from_ci(pr='', include_frameworks=None, exclude_frameworks=None):
    """
    Get test cases, components, and framework in caselink.
    Returns a dict of test cases, array of frameworks, and array of components
    """
    ci_cases = {}
    current_components = []
    current_frameworks = []

    jobs_config_file = os.path.join(config.PATH, 'jobs.yaml')

    test_env = env.Env()

    # Level 1 mean only framework level
    jobs = list(JobGenerator(jobs_config_file, level=1,
                             # TODO: Version and product
                             archs=['x86_64'], products=[('RHEL', '7.3')]).jobs())

    for job in jobs:
        runner_params = Parameters()
        for key, value in job.project.items():
            if value:
                key = key.replace('-', '_')
                runner_params[key] = value

        default_keys = ['img_url', 'rerun', 'update_all_pkgs', 'screenshots_url']
        for key in default_keys:
            try:
                runner_params.pop(key)
            except KeyError:
                pass

        runner_params.update({
            "list": False,
            # Don't let the runner run and exits
            # instead, we prepare the runner manually and extract test cases from it.
            "only": '',
            "no": '',
            "timeout": 600,
            "blacklist": None,
            "img_url": None,
        })  # Custom params

        # Override with some CI param
        runner_params['pr'] = pr

        if include_frameworks and runner_params.test_framework not in include_frameworks:
            continue
        if exclude_frameworks and runner_params.test_framework in exclude_frameworks:
            continue

        test_runner = test_env.prepare_runner(runner_params)
        test_runner.prepare_tests(filter_tests=False)

        if runner_params.test_framework not in current_frameworks:
            current_frameworks.append(runner_params.test_framework)
        if runner_params.component not in current_components:
            current_components.append(runner_params.component)

        for test in test_runner.tests:
            if test in ci_cases.keys():
                LOGGER.info("Duplicated test case name: %s", test)
            ci_cases[test] = {
                'id': test,
                'start_commit': '',  # TODO
                'end_commit': '',  # TODO
                'framework': runner_params.test_framework,
                'archs': [],  # TODO
                'components': [runner_params.component],
            }

    if len(ci_cases) < 1 or len(current_components) < 1 or len(current_frameworks) < 1:
        raise RuntimeError("Can't find any legal auto test case on CI, "
                           "exiting to avoid any risk of current data.")

    return ci_cases, current_components, current_frameworks


def get_tests_from_caselink(params):
    """
    Get test cases, components, and framework in caselink.
    """
    caselink_cases = {}
    caselink_components = []
    caselink_frameworks = []

    res = requests.get(params.caselink_url + '/component/')
    res.raise_for_status()
    for component in res.json()['results']:
        caselink_components.append(component['name'])

    res = requests.get(params.caselink_url + '/framework/')
    res.raise_for_status()
    for framework in res.json()['results']:
        caselink_frameworks.append(framework['name'])

    load_bulk = 300
    next_url_to_get = params.caselink_url + "/auto/?limit=%d" % load_bulk
    while True:
        res = requests.get(next_url_to_get)
        res.raise_for_status()
        LOGGER.info("Processing %s/%s", len(caselink_cases.keys()), res.json()['count'])
        for test in res.json()['results']:
            caselink_cases[test['id']] = test
        next_url_to_get = res.json()['next']
        if not next_url_to_get:
            break

    if len(caselink_cases) < 1 or len(caselink_components) < 1 or len(caselink_frameworks) < 1:
        raise RuntimeError("Can't find any legal auto test case on caselink, "
                           "exiting to avoid any risk of current data.")

    return caselink_cases, caselink_components, caselink_frameworks


def check_pr_closed_on_github(pr_string):
    """
    Return True if pr is legal closed
    """
    try:
        pr_repo, pr_num = pr_string.split()
        pr_repo = GITHUB_REPOS[pr_repo]
    except ValueError:
        LOGGER.error("Illegal pr string: %s", pr_string)
        return False
    except KeyError:
        LOGGER.error("Repo %s not supported.", pr_repo)
        return False
    else:
        _pr = github.PullRequest(pr_repo['project'], pr_repo['repo'], pr_num)
        if _pr.state() == 'closed':
            return True
        return False


def check_error_for_new_pr_cases(pr, new_case_names, caselink_cases):
    for case in new_case_names:
        if case in caselink_cases.keys():
            if caselink_cases[case]['pr'] != pr:
                if caselink_cases[case]['pr']:
                    if check_pr_closed_on_github(caselink_cases[case]['pr']):
                        continue
                    else:
                        LOGGER.error("Case %s added by pull request %s is added by unclosed pr %s",
                                     case, pr, caselink_cases[case]['pr'])
                else:
                    LOGGER.error("Case %s added by pull request %s already exists", case, pr)
                return False
    return True


def check_error_for_del_pr_cases(pr, del_case_names, ci_cases, caselink_cases):
    for case in del_case_names:
        if case in caselink_cases.keys():
            if caselink_cases[case].get('pr', None):
                if caselink_cases[case]['pr'] != pr:
                    if check_pr_closed_on_github(caselink_cases[case]['pr']):
                        continue
                    else:
                        LOGGER.error("Case %s deleted by pr %s is added by another unclosed pr %s",
                                     case, pr, caselink_cases[case]['pr'])
                else:
                    LOGGER.error("BUG:Case %s is being DELETED and ADDED by pr %s ?", case, pr)
                return False
        else:
            LOGGER.error("BUG:Case %s deleted by pull request %s doesn't exists ?", case, pr)
            return False

        for key in UPDATE_KEYS:
            if ci_cases[case][key] != caselink_cases[case][key]:
                LOGGER.error("Case %s deleted by pr %s conflict with caselink.", case, pr)
                return False
    return True


def check_error_for_merged_pr_cases(merged_added_case_names, ci_cases, caselink_cases):
    for case in merged_added_case_names:
        for key in UPDATE_KEYS:
            if ci_cases[case][key] != caselink_cases[case][key]:
                LOGGER.error("Case %s conflict with the one on caselink.", case)
                return False
    return True


def update_meta(params, new_frameworks, new_components):
    for framework in new_frameworks:
        LOGGER.info("Creating new framework: %s", framework)
        res = requests.post(params.caselink_url + "/framework/",
                            json={
                                'name': framework
                            })
        res.raise_for_status()

    for component in new_components:
        LOGGER.info("Creating new component: %s", component)
        res = requests.post(params.caselink_url + "/component/",
                            json={
                                'name': component
                            })
        res.raise_for_status()


def update_main_cases(params, cases_to_delete, cases_to_create, cases_to_update, ci_cases):
    # Make auto cases on caselink same as the auto cases in the master code
    LOGGER.info('%s cases to delete.', len(cases_to_delete))
    for case in cases_to_delete:
        # Don't delete job for other framework
        LOGGER.info('Deleting case: %s', case)
        res = requests.delete(params.caselink_url + "/auto/" + case + "/")
        res.raise_for_status()

    LOGGER.info('%s cases to create.', len(cases_to_create))
    for case in cases_to_create:
        LOGGER.info('Creating case: %s', case)
        res = requests.post(params.caselink_url + "/auto/", json=ci_cases[case])
        res.raise_for_status()

    LOGGER.info('%s cases to update', len(cases_to_update))
    for case in cases_to_update:
        LOGGER.info('Updating case: %s', case)
        res = requests.put(params.caselink_url + "/auto/" + case + "/", json=ci_cases[case])
        res.raise_for_status()


def update_merged_cases(params, pr_merged_added_test_set, pr_merged_deled_test_set):
    for case in pr_merged_added_test_set:
        LOGGER.info("Case %s is merged, ereasing error...", case)
        requests.put(params.caselink_url + "/auto/" + case + "/", json={
            "id": case,
            "errors": []
        })
    for case in pr_merged_deled_test_set:
        LOGGER.info("Deleting %s since pr is deleting it...", case)
        requests.delete(params.caselink_url + "/auto/" + case + "/")


def run(params):
    """
    Main function to list all tests and update caselink DB.
    """
    test_frameworks = utils.split(params.test_frameworks)
    test_frameworks_exclude = utils.split(params.test_frameworks_exclude)

    # Caselink cases With PR
    (caselink_cases, caselink_components, caselink_frameworks) = get_tests_from_caselink(params)

    # Caselink cases Without PR
    caselink_cases_master = {}

    # CI cases Without PR
    (ci_cases, current_components, current_frameworks) = get_tests_from_ci(
        include_frameworks=test_frameworks, exclude_frameworks=test_frameworks_exclude)

    # CI cases With PR
    ci_cases_with_pr, current_components_pr, current_frameworks_pr = {}, [], []

    if params.pr:
        if len(utils.split(params.pr)) != 2:
            LOGGER.error("Caselink update can handle only one pull request at a time!")
            return 1

        ci_cases_with_pr, current_components_pr, current_frameworks_pr = (
            get_tests_from_ci(
                pr=params.pr,
                include_frameworks=test_frameworks, exclude_frameworks=test_frameworks_exclude)
        )

    for case_name, case_attr in caselink_cases.items():
        if not any(err in case_attr['errors'] for err in ["AUTOCASE_PR_NOT_MERGED"]):
            caselink_cases_master[case_name] = case_attr

    ci_cases_master_set = set(ci_cases.keys())
    if params.pr:
        ci_cases_with_pr_set = set(ci_cases_with_pr.keys())
        ci_cases_pr_add_set = set(ci_cases_with_pr_set - ci_cases_master_set)
        ci_cases_pr_del_set = set(ci_cases_master_set - ci_cases_with_pr_set)

    caselink_cases_set = set(caselink_cases.keys())
    caselink_cases_master_set = set(caselink_cases_master.keys())
    caselink_cases_pr_set = caselink_cases_set - caselink_cases_master_set
    caselink_cases_pr_add_set = set()
    caselink_cases_pr_del_set = set()
    caselink_cases_pr_merged_set = set()
    for case in caselink_cases_pr_set:
        if "AUTOCASE_PR_NOT_MERGED" in caselink_cases[case]['errors']:
            caselink_cases_pr_add_set.add(case)
        if "AUTOCASE_DELETED_IN_PR" in caselink_cases[case]['errors']:
            caselink_cases_pr_del_set.add(case)
        if len(caselink_cases[case]['errors']) == 0:
            caselink_cases_pr_merged_set.add(case)
        if case not in (
                caselink_cases_pr_add_set &
                caselink_cases_pr_del_set &
                caselink_cases_pr_merged_set):
            LOGGER.error("Error: Unexpected errors %s", caselink_cases[case]['errors'])

    pr_merged_deled_test_set = set(caselink_cases_pr_del_set - ci_cases_master_set)
    pr_merged_added_test_set = set(caselink_cases_pr_add_set & ci_cases_master_set)

    if params.pr:
        if not check_error_for_new_pr_cases(
                params.pr, ci_cases_pr_add_set, caselink_cases):
            return 1
        if not check_error_for_del_pr_cases(
                params.pr, ci_cases_pr_del_set, ci_cases, caselink_cases):
            return 1

    if not check_error_for_merged_pr_cases(pr_merged_added_test_set, ci_cases, caselink_cases):
        return 1

    new_frameworks = list(
        (set(current_frameworks) | set(current_frameworks_pr)) - set(caselink_frameworks))
    new_components = list(
        (set(current_components) | set(current_components_pr)) - set(caselink_components))

    update_meta(params, new_frameworks, new_components)

    cases_to_delete = set()
    cases_to_create = set()
    cases_to_update = set()

    for case in list(caselink_cases_master_set - ci_cases_master_set):
        framework = caselink_cases[case]['framework']
        if test_frameworks and framework not in test_frameworks:
            continue
        if test_frameworks_exclude and framework in test_frameworks_exclude:
            continue
        cases_to_delete.add(case)

    for case in list(ci_cases_master_set & caselink_cases_master_set):
        for key in UPDATE_KEYS:
            if caselink_cases[case][key] != ci_cases[case][key]:
                cases_to_update.add(case)

    for case in list(ci_cases_master_set - caselink_cases_master_set):
        if case in pr_merged_added_test_set:
            # Use a standlone routine for merged new case.
            continue
        if case not in caselink_cases_pr_set:
            cases_to_create.add(case)

    update_main_cases(params, cases_to_delete, cases_to_create, cases_to_update, ci_cases)
    update_merged_cases(params, pr_merged_added_test_set, pr_merged_deled_test_set)

    if params.pr:
        LOGGER.info('Clean up changes for this PR and resubmit.')
        for case in caselink_cases_set - caselink_cases_master_set:
            if caselink_cases[case]['pr'] == params.pr:
                if "AUTOCASE_PR_NOT_MERGED" in caselink_cases[case]["errors"]:
                    res = requests.delete(params.caselink_url + "/auto/" + case + "/")
                elif "AUTOCASE_DELETED_IN_PR" in caselink_cases[case]["errors"]:
                    res = requests.put(params.caselink_url + "/auto/" + case + "/", json={
                        "id": case,
                        "errors": []
                    })
                res.raise_for_status()

        LOGGER.info('%s cases created by pr %s', len(ci_cases_pr_add_set), params.pr)
        for case in ci_cases_pr_add_set:
            LOGGER.info('Creating case: %s', case)
            json = ci_cases_with_pr[case]
            json["errors"] = ["AUTOCASE_PR_NOT_MERGED"]
            json['pr'] = params.pr
            res = requests.post(params.caselink_url + "/auto/", json=ci_cases_with_pr[case])
            res.raise_for_status()

        LOGGER.info('%s cases deleted by pr %s', len(ci_cases_pr_del_set), params.pr)
        for case in ci_cases_pr_del_set:
            LOGGER.info('Updating case: %s', case)
            json = {
                "id": case,
                "errors": ["AUTOCASE_DELETED_IN_PR"]
            }
            res = requests.put(params.caselink_url + "/auto/" + case + "/", json=json)
            res.raise_for_status()


def parse(parser):
    """
    Parse arguments for generate Jenkins jobs
    """
    parser.add_argument(
        '--caselink-url', dest='caselink_url', action='store',
        default='http://caselink.lab.eng.pek2.redhat.com',
        help='Specify Caselink service\'s URL.')
    parser.add_argument(
        '--test-frameworks', dest='test_frameworks', action='store', default='',
        help="If given, only update test cases for given test frameworks, or update all")
    parser.add_argument(
        '--test-frameworks-exclude', dest='test_frameworks_exclude', action='store',
        default='', help="Exclude specified test framework.")
    parser.add_argument(
        '--pr', dest='pr', action='store', default='',
        help="Merge specified pull requests. Format: 'repo1 pr_id',"
        "only one pull request is allowed for a time. example: 'tp-libvirt 175'")
