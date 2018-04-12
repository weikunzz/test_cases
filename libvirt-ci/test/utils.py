# pylint:disable=missing-docstring

from mock import Mock

MOCK_JOBS = {
'libvirt.acceptance.general': {'Feature': '',
    'Name': 'libvirt.acceptance.general',
    'Only': '',
    'Patches': '',
    'Triggers': 'libvirt'},
'libvirt.acceptance.migration': {'Feature': '',
    'Name': 'libvirt.acceptance.migration',
    'Only': '',
    'Patches': '',
    'Triggers': 'libvirt'},
}

MOCK_PACKAGES = {'libvirt': {'Scratch': 'TRUE',
                                   'Coverage': 'TRUE',
                                   'Debuginfo': 'TRUE',}}

MOCK_PACKAGES_INFO = [{'Brew task ID': '123',
                             'Build': 'libvirt-2.0.0-10.el7_3.5',
                             'Component': 'libvirt',
                             'Product': 'RHEL7.3',
                             'Scratch': 'FALSE',
                             'Coverage': 'FALSE',
                             'Build Date': '3/27/2017 17:28:29',
                             'State': 'Success',
                             'Brew Tags': 'rhel-7.3-z-candidate'}]

MOCK_PRODUCT =  {'RHEL7.2': {'Archs': 'x86_64 ppc64le',
                             'Beaker Distro': 'RHEL-7.2-20151030.0',
                             'CIOS Image': 'rhel-7.2-server-x86_64-released',
                             'RHCS Brew Tag': 'ceph-2-rhel-7-candidate',
                             'RHEL Brew Tag': 'rhel-7.2-z-candidate',
                             'RHEL Supp Brew Tag': 'supp-rhel-7.2-z-candidate',
                             'RHEV-H Brew Tag': 'rhevh-rhel-7.2-candidate',
                             'RHGS Brew Tag': '#rhgs-3.2-rhel-7-candidate (no repo)',
                             'Tree Repo Name': 'RHEL-7.2-20151030.0',
                             'Brew Tag List': 'rhel-7.2-z-candidate\nrhel-7.2-candidate\nsupp-rhel-7.2-z-candidate\nsupp-rhel-7.2-candidate\nrhevh-rhel-7.2-candidate'},
                 'RHEL7.3': {'Archs': 'x86_64 ppc64le',
                             'Beaker Distro': 'RHEL-7.3-20161019.0',
                             'CIOS Image': 'rhel-7.3-server-x86_64-released',
                             'RHCS Brew Tag': 'ceph-2-rhel-7-candidate',
                             'RHEL Brew Tag': 'rhel-7.3-z-candidate',
                             'RHEL Supp Brew Tag': 'supp-rhel-7.3-z-candidate',
                             'RHEV-H Brew Tag': 'rhevh-rhel-7.3-candidate',
                             'RHGS Brew Tag': '#rhgs-3.2-rhel-7-candidate (no repo)',
                             'Tree Repo Name': 'RHEL-7.3-20161019.0',
                             'Brew Tag List': 'rhel-7.3-z-candidate\nrhel-7.3-candidate\nsupp-rhel-7.3-z-candidate\nsupp-rhel-7.3-candidate\nrhevh-rhel-7.3-candidate\nceph-2-rhel-7-candidate\nrhgs-3.2-client-rhel-7-candidate'},}


MOCK_HOSTS = {'1.1.1.1': {'Function': 'Storage',
                          'Server': '1.1.1.1',
                          'Status': ''},
              'host.mock.redhat.com': {'Function': 'Storage',
                                       'Server': 'host.mock.redhat.com',
                                       'Status': ''}}


MOCK_SERVICE_INFO = {'LibvirtCIJobTriggerService': {'API Version': '1',
                                                    'Commands': 'aaa',
                                                    'ENV': 'LIBVIRT_CI_BRANCH=master',
                                                    'Image Tag': 'libvirt_ci/ci',
                                                    'Number': '1',
                                                    'Service Name': 'LibvirtCIJobTriggerService',
                                                    'Token': '',
                                                    'Branch': 'master'},
                     'LibvirtCIRepoUpdaterService': {'API Version': '1',
                                                     'Commands': 'nnnn',
                                                     'ENV': 'LIBVIRT_CI_BRANCH=master',
                                                     'Image Tag': 'libvirt_ci/ci',
                                                     'Number': '1',
                                                     'Service Name': 'LibvirtCIRepoUpdaterService',
                                                     'Token': '',
                                                     'Branch': 'branch1'}}



def mock_gdata_object(*args):
    inst = Mock()
    if args[0] == 'Products':
        inst.fetch.return_value = MOCK_PRODUCT
    elif args[0] == 'Packages':
        inst.fetch.return_value = MOCK_PACKAGES
    elif args[0] == 'Packages Info':
        inst.fetch.return_value = MOCK_PACKAGES_INFO
    elif args[0] == 'Hosts':
        inst.fetch.return_value = MOCK_HOSTS
    elif args[0] == 'Jobs':
        inst.fetch.return_value = MOCK_JOBS
    elif args[0] == 'Service Info':
        inst.fetch.return_value = MOCK_SERVICE_INFO
    else:
        raise Exception("Not support mock %s" % args[0])
    inst.push.return_value = None
    return inst
