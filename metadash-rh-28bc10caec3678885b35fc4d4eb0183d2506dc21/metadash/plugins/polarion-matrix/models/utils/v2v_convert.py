"""
Example Plugin, also used for testing and debug
"""

import itertools


WORKITEM_MAP = {
    'convert_vm_to_libvirt.esx.vm.6_0.linux.7_3.x86_64'
    "RHEL7-80357": 'convert_vm_to_libvirt.xen.vm.$vir_mode.$os_type.$os_version.$vm_arch',
    "RHEL7-98287": 'convert_vm_to_ovirt.xen.vm.$vir_mode.$os_type.$os_version.$vm_arch.$image_format_n.$target_type:raw_f',
    "RHEL7-98288": 'convert_vm_to_ovirt.kvm.$os_type.$os_version.$vm_arch.$image_format_n.$target_type:raw_f',
    "RHEL7-98289": 'convert_vm_to_ovirt.esx.vm.5_1.$os_type.$os_version.$vm_arch.$image_format_n.$target_type:raw_f',
    "RHEL7-80546": 'convert_vm_to_ovirt.esx.vm.5_5.$os_type.$os_version.$vm_arch.$image_format_n.$target_type:raw_f',
    "RHEL7-80547": 'convert_vm_to_ovirt.esx.vm.6_0.$os_type.$os_version.$vm_arch.$image_format_n.$target_type:raw_f',
    "RHEL7-80545": 'convert_vm_to_libvirt.esx.vm.5_1.$os_type.$os_version.$vm_arch',
    "RHEL7-98290": 'convert_vm_to_libvirt.esx.vm.5_5.$os_type.$os_version.$vm_arch',
    "RHEL7-98291": 'convert_vm_to_libvirt.esx.vm.6_0.$os_type.$os_version.$vm_arch',
    "RHEL7-110506": 'convert_vm_to_ovirt.esx.vm.6_5.$os_type$os_version$vm_arch',
    "RHEL7-110507": 'convert_vm_to_libvirt.esx.vm.6_5.$os_type$os_version$vm_arch$image_format_n$target_type:raw_f',
}


def try_get_parameters(pattern, string):
    """
    given string: convert_vm_to_ovirt.xen.vm.pv.linux.5_11.x86_64.raw_f.NFS
    and pattern:  convert_vm_to_ovirt.xen.vm.$vir_mode.$os_type.$os_version.$vm_arch.$target_type

    return { "vir_mode": "pv", "os_type": "linux", "os_version": "5_11", "vm_arch": "x86_64", "target_type": "NFS" }
    If not match, return None
    """
    ret = {}
    test_case_parts = string.split('.')
    pattern_parts = pattern.split('.')

    for testcase, pattern in itertools.zip_longest(test_case_parts, pattern_parts):
        if pattern is None:
            continue
        if pattern.startswith('$'):
            try:
                name, default = pattern[1:].split(':')
            except:
                name, default = pattern[1:], None
            if (default or testcase) is None:
                return None
            ret[name] = default or testcase
        elif pattern != testcase:
            return None
    return ret


def convert_single_testresult(testrun, testresult):
    for workitem, pattern in WORKITEM_MAP.items():
        parameters = try_get_parameters(pattern, testresult.testcase_name)
        if parameters:
            return workitem, parameters
    print(testresult.testcase_name)
    print('!!!!!!!!!!!!!!!!!!!!!')
    return None, {}
