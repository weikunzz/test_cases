"""
Module to manage yum package related manipulations
"""
import re


class PackageError(Exception):
    """
    Exception class for class Package
    """
    pass


class PackageParseError(PackageError):
    """
    Exception class showing the package can't be parsed
    """
    pass


class PackageNotExistsError(PackageError):
    """
    Exception class showing a package does not exists
    """
    pass


def split_nvr(nvr):
    """
    Parse rpm NVR string
    """
    match = re.match(r"^(.+)-([^-]+)-([^-]+)$", nvr)
    if not match:
        raise PackageParseError('NVR %s can not be parsed' % nvr)
    return match.groups()


def any_package(*pkg_names):
    """
    Get a comparable package object matches any name the list
    """
    for pkg_name in pkg_names:
        try:
            return Package.from_name(pkg_name)
        except PackageNotExistsError:
            pass


class Package(object):
    """
    A class to represent a specific version of an yum package
    """
    def __init__(self, name=None, version=None, versions=None, release=None,
                 arch=None):
        if version and versions:
            raise PackageError("Only one of version or versions can be "
                               "specified")
        if version:
            self.version = version
            version_strs = version.split('.')
            versions = []
            for item in version_strs:
                try:
                    versions.append(int(item))
                except ValueError:
                    versions.append(item)
        else:
            if versions is None:
                versions = []
            self.version = '.'.join([str(v) for v in versions])

        self.name = name
        self.versions = versions
        self.release = release
        self.arch = arch
        if all((name, version, release)):
            self.nvr = "-".join((name, version, release))
        else:
            # Dummy package only used for compare version
            self.nvr = None

        self.major, self.minor, self.micro = None, None, None
        try:
            self.major = versions[0]
            self.minor = versions[1]
            self.micro = versions[2]
        except IndexError:
            pass

    @classmethod
    def from_str(cls, string):
        name_regex = r'(?P<name>.+)'
        version_regex = r'(?P<version>[^-]+?)'
        release_regex = r'(?P<release>[^-]+?)'
        arch_str = 'noarch|src|x86_64|aarch64|i686|ppc|ppc64|ppc64le|s390|s390x'
        arch_regex = r'(?P<arch>%s)' % arch_str
        regex = r'^(?:%s-)?(?:%s)(?:-%s)(?:\.%s)?(\.rpm)?$' % (
            name_regex, version_regex, release_regex, arch_regex)
        match = re.match(regex, string)
        name = match.group('name')
        version = match.group('version')
        release = match.group('release')
        arch = match.group('arch')
        return cls(name, version=version, release=release, arch=arch)

    @classmethod
    def from_nvr(cls, nvr):
        name, version, release = split_nvr(nvr)
        return cls(name, version=version, release=release)

    @classmethod
    def from_version(cls, version):
        return cls(version=version)

    def __str__(self):
        res = ''
        if self.name:
            res = self.name
        if self.version:
            if res:
                res += '-'
            res += self.version
        if self.release:
            if res:
                res += '-'
            res += self.release
        if self.arch:
            if res:
                res += '.'
            res += self.arch
        return res

    def __compare_common(self, pkg):
        if isinstance(pkg, str):
            try:
                pkg = Package.from_nvr(pkg)
            except PackageParseError:
                pkg = Package.from_version(pkg)
        elif not isinstance(pkg, Package):
            raise PackageError("A package can only be compared with a package "
                               "or a string, found %s" % type(pkg))
        return pkg

    def __eq__(self, pkg):
        pkg = self.__compare_common(pkg)
        if pkg.name and self.name and pkg.name != self.name:
            return False
        return self.versions == pkg.versions

    def __ne__(self, pkg):
        return not self.__eq__(pkg)

    def __gt__(self, pkg):
        pkg = self.__compare_common(pkg)
        if pkg.name and self.name and pkg.name != self.name:
            raise PackageError("Packages with different names (%s, %s) "
                               "can't be compared" %
                               (self.name, pkg.name))
        return self.versions > pkg.versions

    def __ge__(self, pkg):
        return self.__gt__(pkg) or self.__eq__(pkg)

    def __lt__(self, pkg):
        pkg = self.__compare_common(pkg)
        return pkg.__gt__(self)

    def __le__(self, pkg):
        return self.__lt__(pkg) or self.__eq__(pkg)
