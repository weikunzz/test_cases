"""
Build description generator
"""

import re
import urllib2

from libvirt_ci import package


def gen_patch_desc(patch_url):
    """
    A function to generate patches desc
    """
    patch = urllib2.urlopen(patch_url).read().decode("utf-8")

    desc = '<br>Applied patches:</br>'
    for line in patch.splitlines():
        match = re.match("^Subject: (.+)", line)
        if not match:
            continue
        desc += '<br>%s</br>' % match.group(1)

    desc += '<br/>'
    return desc


def gen_commit_desc(git_commit):
    """
    A function to generate commit desc
    """
    return '<br>Based on commit: %s</br><br/>' % git_commit


def gen_package_desc(pkgs, host):
    """
    A function to generate package version desc
    """
    desc = "<table>"
    for pkg in pkgs:
        try:
            pkg_str = str(package.Package.from_name(pkg, host=host))
        except package.PackageNotExistsError:
            pkg_str = 'not installed'
        desc += "<tr><td>%s</td><td>%s</td></tr>" % (pkg, pkg_str)
    desc += "</table><br/>"
    return desc


def gen_custom_repo_desc(custom_repo):
    """
    A function to generate custom repo desc
    """
    desc = '<br>Custom repo:</br>'
    desc += '<table>'
    for repo in custom_repo.splitlines():
        if not repo:
            continue  # Skip empty lines
        repo_name, repo_url, branch = repo.split()
        desc += '<tr><td>Name:</td><td>%s</td></tr>' % repo_name
        desc += '<tr><td>URL:</td><td>%s</td></tr>' % repo_url
        if ':' in branch:
            branch, commit = branch.split(':', 1)
            desc += '<tr><td>Commit:</td><td>%s</td></tr>' % commit
        desc += '<tr><td>Branch:</td><td>%s</td></tr>' % branch
    desc += '</table><br/>'
    return desc


def run(params):
    """
    Main funcion of description generator
    """
    extra_desc = params.extra_desc
    packages = params.packages.split(',')
    patch_url = params.patch_url
    custom_repo = params.custom_repo
    git_commit = params.git_commit
    host = params.host

    desc = ''
    if patch_url:
        desc += gen_patch_desc(patch_url)
    if git_commit:
        desc += gen_commit_desc(git_commit)
    if custom_repo:
        desc += gen_custom_repo_desc(custom_repo)
    if packages:
        desc += gen_package_desc(packages, host)
    if extra_desc:
        desc += '<br>%s</br>' % extra_desc

    print desc


def parse(parser):
    """
    Parse arguments for description generator
    """
    parser.add_argument(
        '--packages', dest='packages', action='store',
        default='',
        help='Packages version will be list in description')
    parser.add_argument(
        '--patch-url', dest='patch_url', action='store',
        help='Patch URL for applying to latest libvirt repo when testing upstream libvirt')
    parser.add_argument(
        '--extra-desc', dest='extra_desc', action='store',
        default='',
        help='Extra description')
    parser.add_argument(
        '--custom-repo', dest="custom_repo", action='store',
        help='URL and branch for custom git repo. Format: repo url '
        'branch[:commit]')
    parser.add_argument(
        '--git-commit', dest="git_commit", action='store',
        help='Git commit will be tested')
    parser.add_argument(
        '--host', dest="host", action='store',
        help='Remote host name or ip')
