"""
Run a test
"""

import pkgutil

from libvirt_ci import runner
from libvirt_ci import env


def run(params):
    """
    Main function to run test job
    """
    test_env = env.Env(clean=params.clean_env)
    test_runner = test_env.prepare_runner(params)
    if not params.prepare_only:
        test_runner.run()


def parse(parser):
    """
    Parse arguments for running a test job
    """
    frameworks = [name for _, name, _ in
                  pkgutil.iter_modules(runner.__path__)]
    defaults = runner.RunnerBase.defaults
    env_defaults = env.Env.defaults

    # Runner arguments
    shared_group = parser.add_argument_group('Common arguments')
    shared_group.add_argument(
        '--clean-env', dest='clean_env', action='store_true',
        help='Force reset the enviroment')
    shared_group.add_argument(
        '--prepare-only', dest='prepare_only', action='store_true',
        help='Only prepare the enviroment')
    shared_group.add_argument(
        '--rerun', dest='rerun', action='store',
        help='Rerun a job with same configuration as a Jenkins job')
    shared_group.add_argument(
        '--test-framework', dest='test_framework', action='store',
        default=defaults['test_framework'],
        help='Choose test framework for the test. Could be one of %s. '
        'Default to "%s"' % (', '.join(frameworks), defaults['test_framework']))
    shared_group.add_argument(
        '--host', dest='host', action='store',
        default='',
        help='Specify the host for test framework to work, default to "".')
    shared_group.add_argument(
        '--list', dest='list', action='store_true',
        help='List all the test names')
    shared_group.add_argument(
        '--test-objects', dest='test_objects', action='store',
        help="Specify your test objects and their sources, Multiple lines "
             "represents multiple test objects, with each line for one "
             "test object as key-value pairs in the format of "
             "'key1:value1 key2:value2 ...'")
    shared_group.add_argument(
        '--no', dest='no', action='store',
        default=defaults['no'],
        help='Exclude specified tests.')
    shared_group.add_argument(
        '--only', dest='only', action='store',
        default=defaults['only'],
        help='Run only for specified tests.')
    shared_group.add_argument(
        '--no-check', dest='no_check', action='store_true',
        help='Disable checking state changes after each test.')
    shared_group.add_argument(
        '--no-recover', dest='no_recover', action='store_true',
        help='Disable recover state changes after each test.')
    shared_group.add_argument(
        '--fail-diff', dest='fail_diff', action='store_true',
        help='Report tests who do not clean up environment as a failure')
    shared_group.add_argument(
        '--report', dest='report', action='store',
        default=defaults['report'],
        help='Exclude specified tests.')
    shared_group.add_argument(
        '--pr', dest='pr', action='store',
        default=defaults['pr'],
        help="Merge specified pull requests. Format: 'repo1 pr1,pr2 repo2 "
        "pr3,pr4 ...'example: 'tp-libvirt 175,183 avocado-vt 12'")
    shared_group.add_argument(
        '--patch', dest='patch', action='store',
        default=defaults['patch'],
        help="Merge specified patch files. Format: 'repo1 patch1,patch2 repo2 "
        "patch3,patch4 ...'example: 'tp-libvirt 175,183 avocado-vt 12'")
    shared_group.add_argument(
        '--changes', dest='chgs', action='store',
        default=defaults['chgs'],
        help="Cherry pick gerrit changes. Format: 'repo1 change1,change2 "
        "repo2 change3,change4 ...'example: 'libvirt-test-API "
        "refs/changes/72/64672/1'")
    shared_group.add_argument(
        '--retain-vm', dest='retain_vm', action='store_true',
        help='Do not reinstall VM before tests')
    shared_group.add_argument(
        '--pre-cmd', dest='pre_cmd', action='store',
        help='Run a command line after fetch the source code and before '
        'running the test.')
    shared_group.add_argument(
        '--post-cmd', dest='post_cmd', action='store',
        help='Run a command line after running the test')
    shared_group.add_argument(
        '--install-pkgs', dest='install_pkgs', action='store',
        default=defaults['install_pkgs'],
        help='Packages should be installed before test')
    shared_group.add_argument(
        '--update-all-pkgs', dest='update_all_pkgs', action='store_true',
        help='Update all packages before test')
    shared_group.add_argument(
        '--timeout', dest='timeout', action='store',
        default=defaults['timeout'],
        help='Maximum time to wait for one test entry')
    shared_group.add_argument(
        '--replaces', dest='replaces', action='store',
        help='Replace patterns in specified files. This option is only a '
        'placeholder, you should set CI_REPLACES env instead.')
    shared_group.add_argument(
        '--domxml', dest='domxml', action='store',
        help='Customized domain XML')
    shared_group.add_argument(
        '--main-vm', dest='main_vm', action='store',
        help="Customized main domain name.")
    shared_group.add_argument(
        '--netxml', dest='netxml', action='store',
        help='Customized network XML')
    shared_group.add_argument(
        '--net-name', dest='net_name', action='store',
        default=defaults['net_name'],
        help='Run tests using specified network.')
    shared_group.add_argument(
        '--qemu-pkg', dest='qemu_pkg', action='store',
        default=defaults['qemu_pkg'],
        help="Specify with qemu package to be installed. Could be one of "
        "'rhel' or 'rhev'. Default to 'rhev'")
    shared_group.add_argument(
        '--enable-coverage', dest='enable_coverage', action='store_true',
        help='Enable code coverage')
    shared_group.add_argument(
        '--cobertura-xml', dest='cobertura_xml', action='store',
        default="coverage.xml",
        help="cobertura xml path")

    # Env params
    env_group = parser.add_argument_group('Common Env arguments')
    env_group.add_argument(
        '--img-url', dest='img_url', action='store',
        default=env_defaults['img_url'],
        help='Specify a URL to a custom image file')
    env_group.add_argument(
        '--password', dest='password', action='store',
        default=defaults['password'],
        help='Specify a password for logging into guest')
    env_group.add_argument(
        '--test-path', dest='test_path', action='store',
        help='Path for the test directory')
    env_group.add_argument(
        '--custom-repo', dest="custom_repo", action='store',
        default=defaults['custom_repo'],
        help='URL and branch for custom git repo. Format: repo url '
        'branch[:commit]')
    env_group.add_argument(
        '--yum-repos', dest='yum_repos', action='store',
        default=defaults['yum_repos'],
        help='YUM repos setup before test')
    env_group.add_argument(
        '--repo-expire-duration', dest='repo_expire_duration', action='store',
        default=env_defaults['repo_expire_duration'],
        help="Time before a repo is considered expired.")
    env_group.add_argument(
        '--patch-expire-duration', dest='patch_expire_duration', action='store',
        default=env_defaults['patch_expire_duration'],
        help="Time before a applied patch or merged pull request is considered expired.")

    # avocado-vt specific parameters
    avocado_vt_group = parser.add_argument_group(
        'Avocado-vt specific arguments')
    avocado_vt_group.add_argument(
        '--vt-type', dest='vt_type', action='store',
        default=defaults['vt_type'],
        help='Choose test type for virt test. Could be "libvirt", "v2v", '
        '"libguestfs" or "lvsb". Default to "libvirt"')
    avocado_vt_group.add_argument(
        '--vm-type', dest='vm_type', action='store',
        default=defaults['vm_type'],
        help='Choose test machine type, could be i440fx by default, or q35')
    avocado_vt_group.add_argument(
        '--connect-uri', dest='connect_uri', action='store',
        default=defaults['connect_uri'],
        help='Run tests using specified uri.')
    avocado_vt_group.add_argument(
        '--additional-vms', dest='additional_vms', action='store',
        default=defaults['additional_vms'],
        help='Additional VMs for testing')
    avocado_vt_group.add_argument(
        '--smoke', dest='smoke', action='store_true',
        help='Run one test for each script.')
    avocado_vt_group.add_argument(
        '--slice', dest='slice', action='store',
        default=defaults['slice'],
        help='Specify a URL to slice tests.')
    avocado_vt_group.add_argument(
        '--config', dest='config', action='store',
        default=defaults['config'],
        help='Specify a custom Cartesian cfg file')
    avocado_vt_group.add_argument(
        '--os-variant', dest='os_variant', action='store',
        default=defaults['os_variant'],
        help='Specify the --os-variant option when doing virt-install.')
    avocado_vt_group.add_argument(
        '--only-change', dest='only_change', action='store_true',
        help='Only test tp-libvirt test cases related to changed files.')
    avocado_vt_group.add_argument(
        '--screenshots-url', dest='screenshots_url', action='store',
        help='Screenshots to compare with for windows guest check.')
    avocado_vt_group.add_argument(
        '--v2v-vms-src', dest='v2v_vms_src', action='store',
        help='NFS resources of kvm guest images for v2v testing.')
    avocado_vt_group.add_argument(
        '--v2v-vms-list', dest='v2v_vms_list', action='store',
        help='OS version list for testing.')

    # test-api specific parameters
    test_api_group = parser.add_argument_group(
        'libvirt-test-API specific arguments')
    test_api_group.add_argument(
        '--inst-guest-list', dest='inst_guest_list', action='store',
        help='Installation OS version list for testing.')
    test_api_group.add_argument(
        '--inst-arch-list', dest='inst_arch_list', action='store',
        help='Installation OS ARCH list for testing.')

    # Report generating related parameters
    # Thoes parameters won't effect test running, only used for test result collecting
    reporting_group = parser.add_argument_group(
        'Reporting specific arguments, these parameters have no effect on testing, '
        'They are used to store CI parameters in test report'
    )
    reporting_group.add_argument(
        '--component', dest='component', action='store',
        default="libvirt"
    )
    reporting_group.add_argument(
        '--message', dest='message', action='store',
        default="{}"
    )
    reporting_group.add_argument(
        '--product', dest='product', action='store',
        default="Fedora"
    )
    reporting_group.add_argument(
        '--product-version', dest='product_version', action='store',
        default="23"
    )
    reporting_group.add_argument(
        '--show-packages', dest='show_packages', action='store',
        default="libvirt,qemu-kvm,kernel,qemu-kvm-rhev"
    )
    reporting_group.add_argument(
        '--label-package', dest='label_package', action='store',
        default="libvirt"
    )
    reporting_group.add_argument(
        '--job-name', dest='job_name', action='store',
        default="libvirt-ci-standalone-test",
        help="Full job name"
    )
    reporting_group.add_argument(
        '--test-name', dest='test_name', action='store',
        default="standalone-test",
    )
    reporting_group.add_argument(
        '--test-type', dest='test_type', action='store',
        default="standalone"
    )
    reporting_group.add_argument(
        '--test-suffix', dest='test_suffix', action='store',
        default="test"
    )
