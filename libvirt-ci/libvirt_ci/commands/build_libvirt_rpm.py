"""
Libvirt Package builder
"""
import logging
import os
import json
import re
import time
import tempfile

from libvirt_ci import utils
from libvirt_ci import package
from libvirt_ci import metadata

from libvirt_ci.data import REPO_PATH

LOGGER = logging.getLogger(__name__)


def prepare_hosts_info(update_repo=False):
    """
    Prepare dict include hosts info and ansible will need it
    """
    ret_hosts = {'work_host': ['localhost ansible_connection=local']}

    if update_repo:
        storage_hosts = []
        hosts = metadata.Metadata('Hosts').fetch()
        for host_name, host in hosts.items():
            if host['Function'] == 'Storage':
                storage_hosts.append(host_name)
        ret_hosts['storage_host'] = storage_hosts

    return ret_hosts


def prepare_virtcov_patch(libvirt_tag, coverage_pool_addr, virtcov_repo):
    """
    Prepare the virtcov patch.
    Virtcov is a patch use to improve use coverage in libvirt, and it
    include a tools help to generate coverage report
    """
    try:
        # Check if the tag include the nvr info
        _, version, release = package.split_nvr(libvirt_tag)
    except ValueError:
        release = None
        version = None

    # Create a new nvr include virtcov
    if version and release:
        release_list = release.split('.')
        release_list.insert(1, 'virtcov')
        release = '.'.join(release_list)
        version = 'v' + version

    # If doesn't spiecfy version then just use the latest virtcov
    utils.update_git_repo('virtcov', virtcov_repo, version)
    patch_file = os.path.join(REPO_PATH, 'virtcov', 'virtcov.patch')
    if not os.path.isfile(patch_file):
        exit('Patch file %s not exists', patch_file)

    tmp_patch_file = tempfile.NamedTemporaryFile(
        mode='w', suffix='.patch', prefix='libvirt-ci-',
        delete=False)

    # Replace some lines in virtcov patch
    with open(patch_file) as fp:
        lines = fp.readlines()
        for i, line in enumerate(lines):
            if line == '+Release: 1.virtcov%{?dist}%{?extra_release}\n' and release:
                lines[i] = '+Release: %s\n' % release
            elif line == '+COVERAGE_POOL="127.0.0.1:8000"\n' and coverage_pool_addr:
                lines[i] = '+COVERAGE_POOL="%s"\n' % coverage_pool_addr

    tmp_patch_file.writelines(lines)
    tmp_patch_file.close()

    return tmp_patch_file.name


def generate_repo_path(params):
    """
    Generate repo path in the storage host
    """
    if not params.repo_path:
        return params.repo_path

    version = os.environ.get('PROVISION_VERSION')
    product = os.environ.get('PROVISION_PRODUCT')
    if product and version:
        return os.path.join(params.repo_path, product, version)
    else:
        return params.repo_path


def tag_from_ci_message(ci_message):
    """
    Parse CI Message and return tags
    """
    # CI message HEADER include wrong info,
    # we have to parse CI_MESSAGE to get correct info
    ci_data = json.loads(ci_message)
    pretty_data = json.dumps(ci_data, indent=4)
    LOGGER.debug("CI MESSAGE:\n%s", pretty_data)
    libvirt_rpm_name = ci_data['rpms']['x86_64'][0]
    match = re.match(r'^(.+).x86_64.rpm$', libvirt_rpm_name)
    if not match:
        exit('Cannot parse %s' % libvirt_rpm_name)
    # NVR will be a tag in libvirt source code
    nvr = match.groups()[0]
    return nvr


def wait_tag_available(repo_dir, libvirt_repo, tag,
                       interval=60, max_retry=60):
    # Make sure it is not a commit
    if re.match('([a-f0-9]{40})', tag):
        return

    retry = 0
    while True:
        utils.update_git_repo('libvirt', libvirt_repo)
        git_dir = os.path.join(repo_dir, '.git')
        cmd = 'git --git-dir %s tag' % git_dir
        ret = utils.run(cmd)
        tags = ret.stdout.splitlines()
        if tag in tags:
            return

        LOGGER.warning("Tag %s is not available wait %ss to retry. (%s/%s)",
                       tag, interval, retry, max_retry)
        time.sleep(interval)
        retry += 1
        if retry > max_retry:
            raise RuntimeError("Maximum retry exceeded when wait git tag")


def run(params):
    """
    Main funcion of Libvirt Package builder
    """
    patch_url = params.patch_url
    libvirt_repo = params.libvirt_repo
    virtcov = params.virtcov
    git_commit = params.git_commit
    repo_path = generate_repo_path(params)
    coverage_server = params.coverage_server

    local_patch = ''
    rpm_dir = '/root/rpmbuild/RPMS'

    utils.update_git_repo('libvirt', libvirt_repo)
    repo_dir = os.path.join(REPO_PATH, 'libvirt')

    ci_message = os.environ.get('CI_MESSAGE')
    if ci_message:
        git_commit = tag_from_ci_message(ci_message)

    if git_commit:
        wait_tag_available(repo_dir, libvirt_repo, git_commit)

    if virtcov:
        local_patch = prepare_virtcov_patch(git_commit, coverage_server, virtcov)
        # Virtcov use another dir to build rpm
        rpm_dir = '/mnt/coverage/RPMS'

    hosts = prepare_hosts_info(True if repo_path else False)
    arch = [utils.get_arch()]

    utils.run_playbook('build_libvirt_rpm', hosts, arch=arch,
                       private_key='libvirt-jenkins',
                       local_patch=local_patch, patch_url=patch_url,
                       git_repo_path=repo_dir, rpm_dir=rpm_dir,
                       commit=git_commit, repo_path=repo_path, debug=True)


def parse(parser):
    """
    Parse arguments for Libvirt Package builder
    """
    parser.add_argument(
        '--patch-url', dest='patch_url', action='store',
        default='',
        help='Patch URL for applying to libvirt repo')
    parser.add_argument(
        '--libvirt-repo', dest='libvirt_repo', action='store',
        default='git://libvirt.org/libvirt.git',
        help='URL for libvirt git repo')
    parser.add_argument(
        '--virtcov', dest='virtcov', action='store',
        help='Virtcov repo and this will enable libvirt coverage')
    parser.add_argument(
        '--coverage-server', dest='coverage_server', action='store',
        help='Coverage server address')
    parser.add_argument(
        '--git-commit', dest='git_commit', action='store',
        default='origin/master',
        help='Git commit or tag will be used')
    parser.add_argument(
        '--repo-path', dest='repo_path', action='store',
        default='',
        help='Yum repos path on target machine to be updated')
