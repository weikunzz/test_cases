"""
Provision test systems from beaker/openstack and prepare test environment
on them.

When "--target" is bkr/ci-osp, this command will help you to provision a fresh
machine with given parameters.

"--target" could also be hostname or ip address of a remote machine. And this command
can help you to install packages, install libvirt-ci command itself, and run some
playbook to deploy services.

When "--target" is pointed to a beaker machine and "--reprovision" is set, this command
can help you to reinstall OS on target machine with given parameters.

Notice: To provision a specified idle beaker machine, you can use "--target bkr --location <machine>"
or "--target <machine> --reprovision". But hardware related parameters like "--min-mem", "--need_npiv"
are invalided. When using "--location", this command will submit a beaker job, and you job may
hang forever, if the hardware on given machine doesn't need given parameter. When using "--reprovision",
this command will reprovision the target machine and ignore and hardware parameters.

When provision a reserved beaker machine, the beaker machine must be reserved or loaned
by you.

Reprovision non-beaker machine or ci-osp machine is not supported. And mostly like won't be supported.

If any package or credential is needed, this command should guide you to get the credential,
a report an error on missing package.

This command will always install "libvirt-ci", and do some extra setup on target machine,
refer to playbooks/prepare_system.yaml for detail.


Examples:

To provision a new machine on beaker with memory larger than 16G,
disk larger than 200G, with arch x86_64, install RHEL 7.4 with some extra package:
:code:`ci provision --target bkr --product RHEL --version 7.4 --arch x86_64 --min-mem 16000 --min-disk 200000 --ndisk 2 --packages qemu-kvm-rhev,libvirt`


To provision a existing POWER8 machine with RHEL-7.5:
:code:`ci provision --target <machine> --arch ppc64le --product RHEL --version 7.5`


To install some packages on s390x running machine:
:code:`ci provision --target <machine> --packages libvirt,wget --arch s390x --product RHEL-ALT --version 7.5`


To reprovision a existing x86_64 beaker machine locates at CN:
:code:`ci provision --target <beaker_machine> --reprovision --product RHEL --version 7.5 --location CN`

"""
from __future__ import absolute_import

import logging
import collections
import json
import os
import random
import string
import subprocess
import tempfile

from libvirt_ci import metadata
from libvirt_ci import utils
from libvirt_ci import yum_repos
from libvirt_ci import importer

from libvirt_ci.data import RESOURCE_PATH

LOGGER = logging.getLogger(__name__)


def gen_recipeset_repos(params):
    """
    Generate repos part of topology
    """
    # TODO: Use dictionary for arguments
    # pylint: disable=too-many-arguments
    def _gen_tree_repos(product, version, arch,
                        distro, location, repo_type,
                        fallback_distro=None):
        repo = yum_repos.generate_tree_repo(
            product, version,
            arch=arch,
            distro=distro,
            location=location,
            repo_type=repo_type)
        if repo.reachable(arch=arch):
            return repo
        elif fallback_distro:
            LOGGER.warning(
                'Repo %s is not reachable. Trying fallback distro %s',
                repo['baseurl'], fallback_distro)
            _gen_tree_repos(product, version, arch, fallback_distro,
                            location, repo_type)

        raise Exception("Repo %s is not reachable." % repo['baseurl'])

    repos = []
    product_param = metadata.Metadata('Products').get(
        params.product + params.version)
    major, _ = params.version.split('.', 1)

    # Brew repos and EPEL repo are only for RHEL
    # Brew repos are only for RHEL
    if params.product == 'RHEL' or params.product == 'RHEL-ALT':
        # Prepare brew repos, including RHEL and RHEV-H repos
        if params.only_rhel_repos:
            brew_tags = (product_param['RHEL Brew Tag'],)
        else:
            brew_tags = (product_param['RHEL Brew Tag'],
                         product_param['RHEV-H Brew Tag'],
                         product_param['RHGS Brew Tag'],
                         product_param['RHCS Brew Tag'])
        for brew_tag in brew_tags:
            if not brew_tag or brew_tag.startswith("#"):
                continue
            repo = yum_repos.generate_brew_repo(brew_tag, arch=params.arch)
            repos.append(repo)

    # EPEL and Gluster repo are only for RHEL or CentOS
    if params.product in ['RHEL', 'CentOS', 'RHEL-ALT']:
        # Prepare EPEL repo
        repo = yum_repos.generate_epel_repo(version=major, arch=params.arch)
        repos.append(repo)

    # Prepare libvirt-ci repo
    if params.location == 'CN':
        host = '10.66.4.102'
    else:
        host = '10.12.0.20'
    if not params.only_rhel_repos:
        repo_list = yum_repos.generate_libvirt_ci_repos(params.product,
                                                        params.version,
                                                        host=host,
                                                        arch=params.arch)
        repos.extend(repo_list)

    # Prepare tree repo
    if params.beaker_distro:
        distro = params.beaker_distro
    else:
        distro = product_param['Beaker Distro']
    fallback_distro = product_param['Tree Repo Name']
    repo = _gen_tree_repos(params.product, params.version,
                           params.arch, distro, params.location,
                           'Server', fallback_distro)
    repos.append(repo)

    # After RHEL7 some of packages move to Server-optional
    if params.product == 'RHEL' and int(major) >= 7:
        repo = _gen_tree_repos(params.product, params.version,
                               params.arch, distro, params.location,
                               'Server-optional', fallback_distro)
        repos.append(repo)

    # Prepare aarch packages repo
    if "aarch" in params.arch:
        repo = yum_repos.generate_aarch_repo()
        repos.append(repo)

    if params.custom_repos:
        try:
            for repo_name_url in params.custom_repos.split(' '):
                repo_name, repo_url = repo_name_url.split(',', 1)
                repos.append(yum_repos.Repo(repo_name, repo_url))
        except ValueError:
            LOGGER.error('custom-repos not in valid format, should be '
                         '"<repo-name>,<http://repo-address> '
                         '<repo2-name>,<http://repo2-address>"')

    return repos


def setup_params(params):
    """
    Setup parameters according to environmental variables and metadata
    """
    for key, value in params.iteritems():
        env_key = 'PROVISION_' + key.upper()
        new_value = os.environ.get(env_key, value)
        if new_value:
            if isinstance(new_value, (str, unicode)):
                if new_value.lower() == 'true':
                    new_value = True
                elif new_value.lower() == 'false':
                    new_value = False
        setattr(params, key, new_value)

    product_param = metadata.Metadata('Products').get(
        params.product + params.version)
    for key, value in product_param.items():
        setattr(params, key.lower().replace(' ', '_').replace('-', '_'), value)
    if params.distro:
        params.beaker_distro = params.distro
    params.executors = 1
    params.label_name = params.worker_name
    if params.provisioner:
        # set the executors default to 80, all executors been used could cause
        # default medium size vm out of memory, happened on 130 executors
        params.executors = 80
        suffix = ''.join(
            random.choice(string.ascii_lowercase)
            for _ in range(6))
        params.worker_name = 'cios_provisioner_' + suffix
        params.label_name = 'jslave-libvirt'
        params.target = 'ci-osp'
        params.custom_playbook = 'prepare_provisioner'


def run(params):
    """
    Provision a host for testing
    """
    setup_params(params)
    params.yum_repos = gen_recipeset_repos(params)
    connect_timeout = 300

    # Reserve test hosts
    if params.target == 'bkr':
        bkr = importer.import_module("libvirt_ci.provision.beaker")
        reserve_beaker_systems = bkr.reserve_beaker_systems
        build_beaker_xml = bkr.build_beaker_xml
        get_beaker_hub = bkr.get_beaker_hub

        job_xml = build_beaker_xml(params)
        hub = get_beaker_hub()
        job_id, systems = reserve_beaker_systems(job_xml, hub)
        with open(params.env_file, 'a') as env_fp:
            env_fp.write('BEAKER_JOBID=%s\n' % job_id)

        if all(['nay.' in host['system'] or 'pek2.' in host['system']
                for host in systems.values()]):
            params.location = 'CN'

    elif params.target == 'ci-osp':
        osp = importer.import_module("libvirt_ci.provision.osp")
        reserve_openstack_systems = osp.reserve_openstack_systems
        systems = reserve_openstack_systems(params)
        with open(params.env_file, 'a') as env_fp:
            env_fp.write('CIOSP_NODEID=%s\n' % ",".join(systems.keys()))

    elif params.reprovision:
        bkr = importer.import_module("libvirt_ci.provision.beaker")
        reprovisoin_beaker_systems = bkr.reprovisoin_beaker_systems
        connect_timeout = 3600
        if params.location:
            LOGGER.info("--location doesn't work with reprovision: %s",
                        params.target)
        systems = reprovisoin_beaker_systems(params)
        if not systems:
            LOGGER.info("Provision failed!")
            return 1
        systems = {str(idx): {'system': s} for idx, s in enumerate(
            systems)}
    else:
        systems = utils.split(params.target)
        systems = {str(idx): {'system': s} for idx, s in enumerate(systems)}

    # Save test hosts information
    with open(params.hosts_file, 'w') as hosts_fp:
        json.dump(systems, hosts_fp, indent=4)

    # Prepare ansible hosts information
    hosts = collections.defaultdict(list)
    for _, host_info in systems.items():
        if 'whiteboard' in host_info:
            host_type = host_info['whiteboard']
        else:
            host_type = 'worker'
        hosts[host_type].append(host_info['system'])

    # Prepare resource parameters from environ variables
    resource_params = {}
    for key, value in os.environ.items():
        prefix = 'RESOURCE_'
        if key.startswith(prefix):
            key = key[len(prefix):].lower()
            resource_params[key] = value

    # Regenerate repos in case host location changed during provision
    params.yum_repos = gen_recipeset_repos(params)

    # Prepare test hosts environment
    if not params.only_env:
        libvirt_ci_branch = os.environ.get('LIBVIRT_CI_BRANCH', 'master')
        utils.run_playbook('prepare_system', hosts=hosts,
                           private_key='libvirt-jenkins',
                           connect_timeout=connect_timeout,
                           debug=True,
                           env_file=os.path.abspath(params.env_file),
                           jenkins_master=params.jenkins_master,
                           worker_name=params.worker_name,
                           label_name=params.label_name,
                           executors=params.executors,
                           libvirt_ci_branch=libvirt_ci_branch,
                           yum_repos=params.yum_repos,
                           **resource_params)
    if params.custom_playbook:
        utils.run_playbook(params.custom_playbook, hosts=hosts,
                           private_key='libvirt-jenkins',
                           debug=True,
                           env_file=os.path.abspath(params.env_file),
                           worker_name=params.worker_name,
                           libvirt_ci_branch=libvirt_ci_branch,
                           yum_repos=params.yum_repos,
                           **resource_params)
    if params.iscsi or params.nfs:
        # Verify SSH login
        all_hosts = [item for sublist in hosts.values() for item in sublist]
        remote_hosts = set(all_hosts) - set(['localhost', '127.0.0.1'])
        for host in remote_hosts:
            ssh_cmd = 'ssh -q -o PasswordAuthentication=no root@%s exit' % host
            if utils.run(ssh_cmd).exit_code:
                utils.ssh_copy_id('root', host)
        params_template = tempfile.NamedTemporaryFile(
            prefix='libvirt_ci-playbook-', delete=False)
        if params.iscsi:
            iscsi_params_file = os.path.join(
                RESOURCE_PATH,
                'playbooks',
                'vars',
                'iscsi_params.yaml')
            with open(iscsi_params_file, 'r') as f:
                params_template.write(f.read())
        elif params.nfs:
            nfs_params_file = os.path.join(
                RESOURCE_PATH,
                'playbooks',
                'vars',
                'nfs_params.yaml')
            with open(nfs_params_file, 'r') as f:
                params_template.write(f.read())

        params_template.close()

        if params.interactive:
            editor = os.getenv('EDITOR', 'vi')
            subprocess.call('%s %s' % (editor, params_template.name), shell=True)
        if params.iscsi:
            utils.run_playbook('prepare_iscsi', hosts=hosts, debug=True,
                               extra_vars_file=params_template.name)
        elif params.nfs:
            utils.run_playbook('prepare_nfs', hosts=hosts, debug=True,
                               extra_vars_file=params_template.name)


def parse(parser):
    """
    Parse arguments for provision host
    """
    shared_group = parser.add_argument_group('Common options')
    shared_group.add_argument(
        '--target', dest='target', action='store', default='bkr',
        help='Provision target, could be one of bkr, ci-osp or the '
        'hostname/IP of existing machine')
    shared_group.add_argument(
        '--product', dest='product', action='store', default='RHEL',
        help='Provision product name')
    shared_group.add_argument(
        '--version', dest='version', action='store', default='7.4',
        help='Provision product version')
    shared_group.add_argument(
        '--packages', dest='packages', action='store',
        help="A list of packages need to be installed when provisioning "
             "separated by ','.")
    shared_group.add_argument(
        '--provisioner', dest='provisioner', action='store_true',
        help="Whether prepare a test provisioner on Jenkins")
    shared_group.add_argument(
        '--reprovision', dest='reprovision', action='store_true',
        help="Whether reprovision the target or not")
    shared_group.add_argument(
        '--custom-playbook', dest='custom_playbook', action='store',
        help="Path to a custom ansible playbook YAML file to be run "
        "after provisioning")
    shared_group.add_argument(
        '--only-rhel-repos', dest='only_rhel_repos', action='store_true',
        help='Whether need only set up RHEL brew repos')
    shared_group.add_argument(
        '--custom-repos', dest='custom_repos', action='store',
        help='Append some custom repo to the machine')
    shared_group.add_argument(
        '--hosts-file', dest='hosts_file', action='store',
        default='hosts.json',
        help='Where to store hostnames for provisioned hosts')
    parser.add_argument(
        '--jenkins-master', dest='jenkins_master', action='store',
        default='https://libvirt-jenkins.rhev-ci-vms.eng.rdu2.redhat.com',
        help='The URL of Jenkins master for the worker to connect with')
    parser.add_argument(
        '--worker-name', dest='worker_name', action='store',
        default='worker-libvirt',
        help='The name of CI-OSP worker or label of slave for downstream '
        'Jenkins job')
    # This is a temporary solution for Jenkins 3-jobs structure
    # and should be remove after jobs merged
    shared_group.add_argument(
        '--env-file', dest='env_file', action='store', default='env.txt',
        help='Where to store environments for passing to downstream '
        'Jenkins job')

    bkr_group = parser.add_argument_group('Beaker specific target options')
    bkr_group.add_argument(
        '--arch', dest='arch', action='store', default='x86_64',
        help='Provision CPU architecture')
    bkr_group.add_argument(
        '--distro', dest='distro', action='store', default='',
        help='Provision beaker distro name, default from metadata if not given')
    bkr_group.add_argument(
        '--min-mem', dest='min_mem', action='store', default='7000',
        help='Provision required minimum memory size in MB')
    bkr_group.add_argument(
        '--min-disk', dest='min_disk', action='store', default='70000',
        help='Provision required minimum disk size in MB')
    bkr_group.add_argument(
        '--ndisk', dest='ndisk', action='store',
        help='Provision required disk count')
    bkr_group.add_argument(
        '--location', dest='location', action='store', default='',
        help='Provision required machine location. '
             'Could be one of CN, US or ANY')
    bkr_group.add_argument(
        '--job-group', dest='job_group', action='store', default='libvirt-ci',
        help="Job group for beaker. Default to libvirt-ci")
    bkr_group.add_argument(
        '--need-numa', dest='need_numa', action='store_true',
        help='Whether NUMA is required for provisioned machine')
    bkr_group.add_argument(
        '--need-1g-hugepage', dest='need_1g_hugepage', action='store_true',
        help='Whether 1G hugepage is required for provisioned machine')
    bkr_group.add_argument(
        '--ignore-panic', dest='ignore_panic', action='store_true',
        help='Whether ignore panic in beaker job')
    bkr_group.add_argument(
        '--need-cpu-models', dest='need_cpu_models', action='store',
        help='What models of CPU are required for provisioning host')
    bkr_group.add_argument(
        '--need-cpu-vendor', dest='need_cpu_vendor', action='store',
        help='Which CPU vendor, intel, amd, ibm, etc., is required for provisioning host')
    bkr_group.add_argument(
        '--need-westmere', dest='need_westmere', action='store_true',
        help='Whether Westmere CPU is required for provisioned machine')
    bkr_group.add_argument(
        '--need-device-drivers', dest='need_device_drivers', action='store',
        help='What driver of devices are required for provisioning host')
    bkr_group.add_argument(
        '--need-npiv', dest='need_npiv', action='store_true',
        help='Whether NPIV is required for provisioned machine')
    bkr_group.add_argument(
        '--need-sriov', dest='need_sriov', action='store_true',
        help='Whether SR-IOV is required for provisioned machine')
    bkr_group.add_argument(
        '--need-hvm', dest='need_hvm', action='store_true',
        help='Whether HVM is 1 is required for provisioned machine')
    bkr_group.add_argument(
        '--enable-iommu', dest='enable_iommu', action='store_true',
        help='Whether set iommu as on in kernel cmdline for provisioned machine')
    bkr_group.add_argument(
        '--hypervisor', dest='hypervisor', action='store', default='',
        help='Provision machine hypervisor, empty string means a bare metal machine')
    bkr_group.add_argument(
        '--resource-host', dest='resource_host', action='store_true',
        help='Whether need to provision two hosts')
    bkr_group.add_argument(
        '--reserve-days', dest='reserve_days', action='store', default='1',
        help='How many days should a new provisioned machine be reserved, default to 1')

    openstack_group = parser.add_argument_group(
        'OpenStack specific target options')
    openstack_group.add_argument(
        '--flavor', dest='flavor', action='store', default='m1.medium',
        help='Provision required CI-OSP flavor of machine')

    test_env_group = parser.add_argument_group(
        'Testing environment specific options')
    test_env_group.add_argument(
        '--only-env', dest='only_env', action='store_true',
        help='Skip system prepare step, only prepare the testing environment')
    test_env_group.add_argument(
        '--iscsi', dest='iscsi', action='store_true',
        help='Prepare iSCSI testing environment')
    test_env_group.add_argument(
        '--nfs', dest='nfs', action='store_true',
        help='Prepare iSCSI testing environment')
    test_env_group.add_argument(
        '-i', '--interactive', dest='interactive', action='store_true',
        help='let the user edit the config template before run')
