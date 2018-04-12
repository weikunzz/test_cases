"""
Manage yum repo as objects and includes several helper function to generate
useful yum repos.
"""
import ConfigParser
import StringIO
import requests

from . import gdata


class YumRepoError(Exception):
    """
    Exception class for yum repo related errors.
    """


class Repo(dict):
    """
    Class to represent a yum repo with its configuration. This class can also
    be casted as a dictionary
    """
    def __init__(self, name, baseurl, **kwargs):
        repo = {
            'name': name,
            'baseurl': baseurl,
            'enabled': 1,
            'gpgcheck': 0,
            'skip_if_unavailable': 1,
        }
        repo.update(kwargs)
        super(Repo, self).__init__(repo)

    def __getitem__(self, key):
        return dict.__getitem__(self, key)

    def __setitem__(self, key, val):
        dict.__setitem__(self, key, val)

    def update(self, **kwargs):
        for key, value in kwargs.iteritems():
            self[key] = value

    def reachable(self, arch='x86_64', version='7'):
        """
        Test whether the repo URL is reachable
        """
        url = self['baseurl']
        if '$basearch' in url:
            url = url.replace('$basearch', arch)
        if '$releasever' in url:
            url = url.replace('$releasever', version)
        response = requests.head(url)
        return response.status_code == 200 or response.status_code == 302

    def gen_yum_config(self):
        name = self['name'].replace(' ', '-')
        config = ConfigParser.RawConfigParser()
        config.add_section(self['name'])
        buf = StringIO.StringIO('\n')
        for key, value in self.items():
            config.set(name, key, value)
        config.write(buf)
        return buf.getvalue()


def generate_brew_repo(brew_tag, **kwargs):
    """
    Generate repo for brew
    """
    if 'arch' in kwargs:
        arch = kwargs['arch']
    else:
        arch = '$basearch'
    repo_url = ('http://download.eng.bos.redhat.com/rel-eng/repos/'
                '%s/%s/' % (brew_tag, arch))
    if 'name' in kwargs:
        name = kwargs['name']
        kwargs.pop('name')
    else:
        name = 'brew_' + brew_tag
    return Repo(name, repo_url, **kwargs)


def generate_libvirt_ci_repos(product, version,
                              host='download.libvirt.redhat.com',
                              arch=None):
    """
    Generate repo list for specific use in libvirt CI
    """
    repo_list = []

    repo = generate_ci_repo(product, version, host=host, arch=arch)
    repo_list.append(repo)

    if product == 'RHEL-ALT':
        # RHEL-ALT repo only have few packages right now, that means we need
        # use it with RHEL repo
        repo = generate_ci_repo('RHEL', version, host=host, arch=arch, name='libvirt_ci_extra')

        # This will exclude the packages which in RHEL-ALT repo in RHEL repo
        # To avoid install the rhel packages
        pkg_info = gdata.GData('Packages Info').fetch()
        exclude_pkgs = pkg_info.filter(Product=product + version)
        pkgs_set = set([pkg['Component'] for pkg in exclude_pkgs])
        exclude_str = ' '.join(['%s*' % pkg_name for pkg_name in pkgs_set])

        # Check extra pkgs
        pkgs_data = gdata.GData('Packages').fetch()
        for pkg in pkgs_set:
            if pkg in pkgs_data.keys() and pkgs_data[pkg]['Extra pkgs']:
                for package in pkgs_data[pkg]['Extra pkgs'].split():
                    exclude_str += ' %s*' % package

        repo['exclude'] = exclude_str + ' ' + repo['exclude']

        # Set the RHEL-ALT repo with highest priority
        repo_list[0]['priority'] = 1

        repo_list.append(repo)
    return repo_list


def generate_epel_repo(version=None, arch=None):
    """
    Generate repo for EPEL
    """
    if not version:
        version = "$releasever"
    if not arch:
        arch = '$basearch'
    url = 'http://dl.fedoraproject.org/pub/epel/%s/%s/' % (version, arch)
    return Repo('epel', url)


def generate_tree_repo(product, version, arch=None, distro='', location='US', repo_type='Server'):
    """
    Generate repo for a product package tree
    """
    name = 'tree-'
    if distro.split('.')[-2] == 'n':
        tree = 'nightly'
    else:
        tree = 'rel-eng'
    if not arch:
        arch = '$basearch'
    if product == 'RHEL':
        if location == 'CN':
            repo_url = 'http://download.eng.pek2.redhat.com/pub/rhel/%s/' % tree
        else:
            repo_url = 'http://download.eng.bos.redhat.com/%s/' % tree
        repo_url += '%s/compose/%s/%s/os/' % (distro, repo_type, arch)
    elif product == 'Fedora':
        if location == 'CN':
            repo_url = 'http://download.eng.pek2.redhat.com/pub/fedora/linux/'
        else:
            repo_url = 'http://download.eng.bos.redhat.com/pub/fedora/linux/'
        repo_url += 'releases/%s/%s/%s/os/' % (version, repo_type, arch)
    elif product == 'RHEL-ALT':
        repo_url = 'http://download.eng.bos.redhat.com/%s/' % tree
        repo_url += '%s/compose/%s/%s/os/' % (distro, repo_type, arch)
    else:
        raise YumRepoError("Unknown product %s" % product)
    name += '%s-%s-%s' % (product, version, repo_type)
    if distro:
        name += '-' + distro
    return Repo(name, repo_url)


def generate_rhpkg_repo():
    url = 'http://download.lab.bos.redhat.com/rel-eng/dist-git/rhel/$releasever/'
    return Repo('rhpkg', url)


def generate_aarch_repo():
    url = 'http://batcave.lab.eng.brq.redhat.com/repos/preview/rhelsa/'
    return Repo('aarch', url)


def generate_ci_repo(product, version, host='download.libvirt.redhat.com', arch=None, name='libvirt_ci'):
    if not arch:
        arch = '$basearch'
    repo_url = ('http://%s/libvirt-CI-repos/'
                '%s/%s/%s/' % (host, product, version, arch))
    pkg_info = gdata.GData('Packages Info').fetch()
    exclude_pkgs = pkg_info.filter(Product=product + version, Exclude=True)
    exclude_str = ' '.join([pkg['Exclude'] for pkg in exclude_pkgs])
    return Repo(name, repo_url, exclude=exclude_str)
