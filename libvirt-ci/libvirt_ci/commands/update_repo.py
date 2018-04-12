#!/usr/bin/env python
"""
Update custom yum repos on specified storages servers
"""
import logging
import collections
import os
import re
import threading
from dateutil import parser as date_parser

import jinja2

from libvirt_ci import gdata
from libvirt_ci import mail
from libvirt_ci import metadata
from libvirt_ci import package
from libvirt_ci import utils
from libvirt_ci import yum_repos

from libvirt_ci.data import RESOURCE_PATH

LOGGER = logging.getLogger(__name__)


def get_latest_packages(product_version):
    """
    Get latest packages build names from brew
    """
    product_param = metadata.Metadata('Products').get(product_version)
    tags = [product_param[title] for title in product_param.keys()
            if title.endswith('Brew Tag') and product_param[title]]
    pkgs = {}
    for tag in tags:
        cmd = 'brew latest-build --all --quiet ' + tag
        LOGGER.info('Loading latest packages for brew tag %s', tag)
        result = utils.run(cmd)
        output = result.stdout
        for line in output.splitlines():
            pkg_tuple = line.strip().split()
            if pkg_tuple:
                nvr, _, _ = pkg_tuple
                pkg = package.Package.from_str(nvr)
                if pkg.name in pkgs:
                    last_nvr = pkgs[pkg.name]
                    last_pkg = package.Package.from_str(last_nvr)
                    if pkg > last_pkg:
                        LOGGER.info('Using %s instead of %s', pkg, last_pkg)
                        pkgs[pkg.name] = nvr
                else:
                    pkgs[pkg.name] = nvr
    return pkgs


def get_build_info(nvr):
    """
    Get specify build information
    """
    cmd = 'brew buildinfo ' + nvr
    LOGGER.info('Check %s build information', nvr)
    result = utils.run(cmd)
    if result.exit_status != 'success':
        LOGGER.error('Fail to check build info:\n%s', result)
        return
    output = result.stdout

    task_id = None
    brew_tag = None
    finished_time = None
    rpms = []

    for line in output.splitlines():
        match = re.match(r'^Task: (\d+) build \((.+), (.+)\)', line)
        if match:
            task_id = int(match.group(1))
            brew_tag = match.group(2)
            continue

        match = re.match('^Finished: (.+)$', line)
        if match:
            finished_time = date_parser.parse(match.group(1)).strftime('%Y-%m-%d %H:%M:%S')
            continue

        match = re.match('(.+)/([^/]+.rpm)$', line)
        if match:
            rpms.append(match.group(2))

    return task_id, brew_tag, finished_time, rpms


def get_updated_packages(recorded_packages, latest_packages,
                         product_version, package_watchers,
                         repo_path, pkg_list):
    """
    Filter out newly updated packages and update pkg_list
    """
    build_names = []
    for pkg_info in recorded_packages:
        if pkg_info['Product'] != product_version:
            continue
        if pkg_info['Scratch'] == 'TRUE':
            continue
        build_names.append(pkg_info['Build'])

    for pkg, pkg_nvr in latest_packages.items():
        if pkg not in package_watchers:
            LOGGER.warn("Package %s is not watched by anyone", pkg)
            continue
        if pkg_nvr in build_names:
            continue

        # Check if there is the same package need update
        if pkg_nvr in pkg_list:
            if repo_path not in pkg_list[pkg_nvr]['repo_list'].values():
                pkg_list[pkg_nvr]['repo_list'][product_version] = repo_path
        else:
            pkg_list[pkg_nvr] = {'name': pkg,
                                 'repo_list': {product_version: repo_path}}


def update_packages(arches, repo_list, pkg=None,
                    task_id=None, debug_info=False, scratch=False,
                    prepare_pkgs=True, create_repo=True):
    """
    Update packages on storage servers.
    """
    storage_hosts = []
    hosts = metadata.Metadata('Hosts').fetch()
    for host_name, host in hosts.items():
        if host['Function'] == 'Storage':
            storage_hosts.append(host_name)

    kargs = {'private_key': 'libvirt-jenkins',
             'arch': arches,
             'repo_list': repo_list}
    extra_opt = '--quiet'
    if debug_info:
        extra_opt += ' --debuginfo'
    if prepare_pkgs:
        kargs['prepare_pkgs'] = 'true'
    if create_repo:
        kargs['create_repo'] = 'true'
    if pkg:
        kargs['package'] = pkg
    elif task_id:
        if scratch:
            # For scratch build we cannot use download-build
            kargs['task_id'] = task_id
        else:
            extra_opt += ' --task-id'
            kargs['package'] = task_id
    kargs['extra_opt'] = extra_opt

    utils.run_playbook('update_custom_repo', storage_hosts, **kargs)


def update_single_pkgs(pkg_name, repo_list, pkgs_info, pkg_nvr,
                       task_id=None, arches=None, scratch=False,
                       coverage=False, brew_tag=None, build_date=None,
                       mail_notify=False, debug_info=False,
                       prepare_pkgs=True, create_repo=True, latest_pkgs=None):
    """
    Update a package to several repo
    """
    if not arches:
        arches = ['ppc64le', 'x86_64', 'aarch64']

    LOGGER.info("Updating repo for packages: %s", pkg_nvr)
    kargs = {'debug_info': debug_info,
             'scratch': scratch,
             'prepare_pkgs': prepare_pkgs,
             'create_repo': create_repo}
    if task_id:
        kargs['task_id'] = task_id
    else:
        kargs['package'] = pkg_nvr

    try:
        update_packages(arches, repo_list.values(), **kargs)
    except utils.CmdError as detail:
        LOGGER.error('Update yum repo failed:\n%s', detail)
        state = 'Fail'
    else:
        state = 'Success'

    pkgs_data = pkgs_info.fetch()
    for product_version in repo_list.keys():
        # Update information to google spread sheet
        info = {'Brew task ID': task_id if task_id else '',
                'Build': pkg_nvr,
                'Component': pkg_name,
                'Product': product_version,
                'Scratch': str(scratch),
                'Coverage': str(coverage),
                'Build Date': build_date if build_date else '',
                'State': state,
                'Brew Tags': brew_tag if brew_tag else ''}
        if latest_pkgs:
            cur_pkg = latest_pkgs.setdefault(product_version, {}).setdefault(pkg_name)
            new_pkg = package.Package.from_nvr(pkg_nvr)
            if not cur_pkg or cur_pkg < new_pkg:
                latest_pkgs[product_version][pkg_name] = new_pkg
        pkgs_data.append(info)
    pkgs_info.push(pkgs_data)

    if mail_notify and brew_tag and (not scratch or coverage):
        package_watchers = get_package_watchers()
        watchers = package_watchers[pkg_name]
        LOGGER.warn("Package %s is watched by %s",
                    pkg_name, ','.join(watchers))
        email_notify(watchers, pkg_name, pkg_nvr,
                     brew_tag, transfer_url(repo_list),
                     scratch, task_id, latest_pkgs)


def transfer_url(repo_list):
    """
    Convert a list of repo dir link to http url
    """
    fix_repo_list = {}

    storage_hosts = []
    hosts = metadata.Metadata('Hosts').fetch()
    for host_name, host in hosts.items():
        if host['Function'] == 'Storage':
            storage_hosts.append(host_name)

    for name, repo_url in repo_list.items():
        match = re.match('^/srv/www/html/(.+)$', repo_url)
        if not match:
            raise Exception('Cannot transfer repo_url: ' + repo_url)
        repo_dir = match.group(1)
        for index, host in enumerate(storage_hosts):
            trans_url = 'http://%s/%s' % (host, repo_dir)
            fix_repo_list['CI-%s-%d' % (name, index + 1)] = trans_url

    return fix_repo_list


def update_all_pkgs(base_repo_path, mail_notify=False):
    """
    Update the repo of a specific product-version.
    """
    products = get_all_products(True)

    pkgs_info = gdata.GData('Packages Info')
    pkg_data = gdata.GData('Packages')
    arches = ['ppc64le', 'x86_64', 'aarch64']
    data = pkg_data.fetch()
    pkg_list = {}
    for product, version in products:
        product_version = product + version
        repo_path = os.path.join(base_repo_path, product, version)

        LOGGER.info("=" * 80)
        LOGGER.info("Checking latest packages for %s", product_version)
        LOGGER.info("-" * 80)

        # Get latest packages for specified RHEL version
        package_watchers = get_package_watchers()
        latest_packages = get_latest_packages(product_version)
        recorded_packages = pkgs_info.fetch()
        get_updated_packages(recorded_packages, latest_packages,
                             product_version, package_watchers,
                             repo_path, pkg_list)

    if not pkg_list:
        LOGGER.info("No package need update")
        return

    thread_pool = []
    updated_repos = set()
    for pkg_nvr, info in pkg_list.items():
        if info['name'] in data.keys() and data[info['name']]['Debuginfo'] == 'TRUE':
            debug_info = True
        else:
            debug_info = False
        updated_repos = updated_repos ^ set(info['repo_list'].values())

        task_id, brew_tag, finished_time, _ = get_build_info(pkg_nvr)
        kwargs = {'debug_info': debug_info,
                  'create_repo': False,
                  'task_id': task_id,
                  'brew_tag': brew_tag,
                  'build_date': finished_time,
                  'mail_notify': mail_notify}
        # Use multi-thread to update packages
        th = threading.Thread(target=update_single_pkgs,
                              args=(info['name'], info['repo_list'],
                                    pkgs_info, pkg_nvr,),
                              kwargs=kwargs)
        th.start()
        thread_pool.append(th)

    for th in thread_pool:
        th.join()

    update_packages(arches, list(updated_repos), prepare_pkgs=False)


def get_all_products(split=False):
    """
    Get all products in database
    """
    product_versions = metadata.Metadata('Products').fetch().keys()
    if not split:
        return product_versions

    ret_list = []
    for pv in product_versions:
        match = re.match(r'^([a-zA-Z]+)([\d\.]+)$', pv)
        if not match:
            raise Exception("Invalid product version %s" % pv)
        ret_list.append(match.groups())
    return ret_list


def get_products(brew_tag, version, product):
    """
    Get products whose yum repo need to be updated.
    """
    if not brew_tag:
        brew_tag = os.environ.get('target')

    if brew_tag:
        LOGGER.info("Target brew tag is %s", brew_tag)
        versions = re.findall(r'rhel-(\d+)(?:\.(\d+))?', brew_tag.lower())
        if not versions:
            raise Exception("Not found version in brew tag %s" % brew_tag)
        else:
            assert len(versions) == 1
            major, minor = versions[0]
    else:
        major, minor = version.split('.')

    version = ''
    if major:
        version += major
    if minor:
        version += '.' + minor

    products = get_all_products()
    return [(product, p[len(product):])
            for p in products if product + version in p]


def get_package_watchers():
    """
    Get all the packages being watching and their watchers as a dictionary.

    The keys of result is packages under watching, and the values are lists of
    people who are watching specific package.
    """
    people = metadata.Metadata('People').fetch()
    groups = metadata.Metadata('Groups').fetch()
    subscriptions = collections.defaultdict(set)
    for member, info in people.items():
        joined_groups = ['libvirt'] + utils.split(info['Groups'])
        for group in joined_groups:
            for pkg in utils.split(groups[group]['Watching Packages']):
                subscriptions[pkg].add(member)
        for pkg in utils.split(info['Watching Packages']):
            subscriptions[pkg].add(member)
    return subscriptions


# pylint: disable=unused-argument
def email_notify(watchers, pkg, nvr, tag, repo_list,
                 scratch=False, task_id=None, latest_pkgs=None):
    """
    Send email notification about the new package to watchers
    """
    # Example subject: [NEW BUILD] [libvirt] libvirt-3.0.1-2.el7
    subject = '[NEW BUILD] [%s] %s' % (pkg, nvr)
    repo_list_text = ''
    attch_repo = []

    # Prepare the repo need attached
    for name, repo_url in repo_list.items():
        repo_list_text += '%s: %s\n' % (name, repo_url)
        fixed_repo_url = '%s/$basearch' % repo_url
        repo_conf = yum_repos.Repo(name, fixed_repo_url).gen_yum_config()
        attch_repo.append((name + '.repo', repo_conf,))

    repo_conf = yum_repos.generate_rhpkg_repo().gen_yum_config()
    attch_repo.append(('rhpkg.repo', repo_conf,))

    # Create brew command
    if scratch:
        if not task_id:
            raise Exception('Cannot generate cmd without task id')
        brew_cmd = 'brew download-task --arch=&lt;your_arch&gt; ' + str(task_id)
    else:
        brew_cmd = 'brew download-build --arch=&lt;your_arch&gt; ' + nvr

    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            os.path.join(RESOURCE_PATH, 'templates')))
    # pylint: disable=no-member
    template = jinja_env.get_template('package_notification_email.html')
    text = template.render(
        repo_list=repo_list_text,
        package=pkg,
        brew_cmd=brew_cmd,
    )
    mail.send(watchers, subject=subject, text=text, mimetype='html', attachments=attch_repo)


def run(params):
    """
    Main function to update custom yum repos
    """
    repo_path = params.repo_path

    update_all_pkgs(repo_path, params.email_notify)


def parse(parser):
    """
    Parse arguments for updating custom yum repos
    """
    parser.add_argument(
        '--repo-path', dest='repo_path', action='store',
        default='/srv/www/html/libvirt-CI-repos',
        help='Yum repos path on target machine to be updated')
    parser.add_argument(
        '--email-notify', dest='email_notify', action='store_true',
        help='Enable email notify')
