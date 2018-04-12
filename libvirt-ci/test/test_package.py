# pylint:disable=missing-docstring

import pytest
from pytest import raises
import mock

from libvirt_ci import package
from libvirt_ci import utils


def test_init():
    # We can init an empty package
    pkg = package.Package()
    assert str(pkg) == ''

    # We can init a package with only name specified
    package.Package('libvirt')

    # We can specify the version by a string
    package.Package('libvirt', version='1.2.3')

    # We can specify the version with out a name
    package.Package(version='1.2.3')

    # We can specify the version by a tuple
    package.Package('libvirt', versions=(1, 2, 3))

    # We can specify the release and arch
    pkg = package.Package('libvirt', version='1.2.3', release='1.el7',
                          arch='aarch64')
    assert str(pkg) == 'libvirt-1.2.3-1.el7.aarch64'

    # We can't specify both version and versions
    with raises(package.PackageError):
        package.Package('libvirt', version='1.2.3', versions=(1, 2, 3))

def test_from_str():
    nvrs = [
        'libcanberra-gtk2-0.30-5.el7.x86_64',
        'libcdio-paranoia-10.2+0.90-11.el7.x86_64',
        'erlang-inets-R16B-03.16.el7.x86_64',
        'rng-tools-5-7.el7.x86_64',
    ]
    # Uncomment this line to enable a larger scale (non-unit) tests
    # nvrs = utils.run('rpm -qa').stdout.splitlines()
    for nvr in nvrs:
        pkg = package.Package.from_str(nvr)
        assert nvr == str(pkg)

        pkg.name = None
        no_name_pkg = package.Package.from_str(str(pkg))
        assert str(no_name_pkg) == str(pkg)
        assert no_name_pkg.name == pkg.name
        assert no_name_pkg.version == pkg.version
        assert no_name_pkg.release == pkg.release
        assert no_name_pkg.arch == pkg.arch

        pkg.arch = None
        no_name_arch_pkg = package.Package.from_str(str(pkg))
        assert str(no_name_arch_pkg) == str(pkg)
        assert no_name_arch_pkg.name == pkg.name
        assert no_name_arch_pkg.version == pkg.version
        assert no_name_arch_pkg.release == pkg.release
        assert no_name_arch_pkg.arch == pkg.arch

    a_str = 'a-1-7.el7'
    a = package.Package.from_str(a_str)
    assert a.name == 'a'
    assert a.version == '1'
    assert a.release == '7.el7'
    assert a.arch == None

    a_str = '1-7.el7'
    a = package.Package.from_str(a_str)
    assert a.name == None
    assert a.version == '1'
    assert a.release == '7.el7'
    assert a.arch == None

def test_from_nvr():
    nvrs = [
        'libcanberra-gtk2-0.30-5.el7.x86_64',
        'libcdio-paranoia-10.2+0.90-11.el7.x86_64',
        'erlang-inets-R16B-03.16.el7.x86_64',
        'rng-tools-5-7.el7.x86_64',
    ]
    for nvr in nvrs:
        pkg = package.Package.from_nvr(nvr)
        assert nvr == str(pkg)

def test_from_name():
    with mock.patch('libvirt_ci.utils.run') as mock_run:
        mock_run.return_value.exit_code = 0
        mock_run.return_value.stdout = (
            "kernel-3.10.0-332.el7.x86_64\n"
            "kernel-3.10.0-327.el7.x86_64\n"
            "kernel-3.10.0-333.el7.x86_64")
        package.Package.from_name('kernel')

        mock_run.return_value.stdout = "libvirt-2.0.0-10.el7.x86_64"
        package.Package.from_name('libvirt')

        mock_run.return_value.stdout = "UNKNOWN OUTPUT"
        with raises(package.PackageParseError):
            package.Package.from_name('libvirt')

        mock_run.return_value.exit_code = 1
        with raises(package.PackageNotExistsError):
            package.Package.from_name('NON EXISTS PACKAGE')

def test_any_package():
    assert package.any_package() == None

    results = []
    result = utils.CmdResult('mock_result')
    result.exit_code = 1
    results.append(result)

    result = utils.CmdResult('mock_result')
    qemu_version = "qemu-kvm-rhev-2.6.0-24.el7.x86_64"
    result.exit_code = 0
    result.stdout = qemu_version
    results.append(result)

    with mock.patch('libvirt_ci.utils.run') as mock_run:
        mock_run.side_effect = results
        pkg = package.any_package('qemu-kvm', 'qemu-kvm-rhev')
        assert pkg == qemu_version

def test_compare():
    a1_str = 'a-1.2-1.el7.x86_64'
    a1 = package.Package.from_nvr(a1_str)
    a2 = package.Package.from_nvr('a-2-1.el7.x86_64')
    b1 = package.Package.from_nvr('b-1.2-1.el7.x86_64')

    # A package will always equal to itself
    assert a1 == a1

    # Two packages are not equal if their names are not the same
    # even if their versions are the same
    assert a1.versions == b1.versions
    assert a1 != b1

    # A package can be compared with a string
    assert a1 == a1_str
    # A package can be compared with a version string
    assert a1 == a1.version
    # A package can not be compared with a number
    with raises(package.PackageError):
        assert a1 == 1.2

    assert a2 > a1
    assert a1 <= a2
    assert a2 >= a1_str
    assert b1 < '1.10'

    with raises(package.PackageError):
        a1 > b1
    with raises(package.PackageError):
        a1_str > b1
