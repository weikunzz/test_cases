"""
Module for beaker machine provision
"""
from __future__ import absolute_import

import logging
import json
import os
import signal
import sys
import time
import getpass
import subprocess
import krbV
import urllib
import requests
from xml.dom import minidom

from lxml import etree
# pylint:disable=import-error
from bkr.common.hub import HubProxy
from bkr.common.pyconfig import PyConfigParser
from bkr.client import BeakerCommand

from libvirt_ci import utils
from libvirt_ci import package

LOGGER = logging.getLogger(__name__)

KS_APPEND_DEFAULT = """
%post
# Avoid yum install i686 package on 64 bit system
echo multilib_policy=best >> /etc/yum.conf

# Beaker task repo could be removed anytime
echo skip_if_unavailable = 1 >> /etc/yum.repos.d/beaker-tasks.repo

# Fake a .redhat.com hostname for nearest storage server
if [[ `hostname` =~ .*(nay|pek2).redhat.com$ ]]
then
    echo 10.66.4.102 download.libvirt.redhat.com >> /etc/hosts
else
    echo 10.12.0.20  download.libvirt.redhat.com >> /etc/hosts
fi
%end

"""

KS_APPEND_GRUB2 = """
%post
# Add iommu kernel option
vendor=`cat /proc/cpuinfo | grep vendor | uniq | awk -F': ' '{print $2}'`
if [[ $vendor =~ .*Intel$ ]]
then
    echo 'GRUB_CMDLINE_LINUX_DEFAULT="intel_iommu=on"' >>  /etc/default/grub
elif [[ $vendor =~ .*AMD$ ]]
then
    echo 'GRUB_CMDLINE_LINUX_DEFAULT="amd_iommu=on"' >>  /etc/default/grub
else
    echo 'Skip iommu kernel command line setup'
fi
grub2-mkconfig -o /boot/grub2/grub.cfg
%end
"""

KS_APPEND_GRUB = r"""
%post
# Add iommu kernel option
vendor=`cat /proc/cpuinfo | grep vendor | uniq | awk -F': ' '{print $2}'`
if [[ $vendor =~ .*Intel$ ]]
then
    sed -ie 's/^\s\+kernel.*$/& intel_iommu=on/g' /boot/grub/grub.conf
elif [[ $vendor =~ .*AMD$ ]]
then
    sed -ie 's/^\s\+kernel.*$/& amd_iommu=on/g' /boot/grub/grub.conf
else
    echo 'Skip iommu kernel command line setup'
fi
%end
"""


def fill_ks_appends(ks_appends, params):
    """
    Fill ks appends element for beaker job XML according to parameters
    """
    ks_append = etree.SubElement(ks_appends, 'ks_append')
    append_context = KS_APPEND_DEFAULT
    if params.enable_iommu:
        if 'RHEL-6' in params.beaker_distro:
            append_context += KS_APPEND_GRUB
        else:
            append_context += KS_APPEND_GRUB2
    ks_append.text = etree.CDATA(append_context)


def fill_repos(repos, params):
    """
    Fill repos element for beaker job XML according to parameters
    """
    repo_list = params.yum_repos
    if repo_list:
        for repo_dict in repo_list:
            repo = etree.SubElement(repos, 'repo')
            repo.set('name', repo_dict['name'])
            repo.set('url', repo_dict['baseurl'])


def fill_packages(packages, params):
    """
    Fill packages element for beaker job XML according to parameters
    """
    pkg_names = set([
        'libselinux-python', 'gmp-devel', 'xz-devel'])
    if params.packages:
        pkg_names.update(params.packages.split(','))
    for pkg_name in pkg_names:
        package_ele = etree.SubElement(packages, 'package')
        package_ele.set('name', pkg_name)


def fill_distro_requires(distro_requires, params):
    """
    Fill distro requires element for beaker job XML according to parameters
    """
    and_op = etree.SubElement(distro_requires, 'and')
    requirements = ['distro_variant = Server']
    if params.arch:
        requirements.append('distro_arch = ' + params.arch)
    if params.beaker_distro:
        requirements.append('distro_name = ' + params.beaker_distro)

    for requirement in requirements:
        key, op, value = requirement.split()
        require = etree.SubElement(and_op, key)
        require.set("op", op)
        require.set("value", value)


def fill_host_requires(host_requires, params):
    """
    Fill host requires element for beaker job XML according to parameters
    """
    # Process host location filter
    controllers = []
    if params.location in ['ANY', '']:
        pass
    elif params.location == 'CN':
        controllers.append('lab-01.rhts.eng.pek2.redhat.com')
    elif params.location == 'US':
        controllers.append('lab-02.rhts.eng.bos.redhat.com')
        controllers.append('lab-02.rhts.eng.rdu.redhat.com')
    else:
        host_requires.set('force', params.location)
        # Don't need to filter host if specified
        return

    and_op = etree.SubElement(host_requires, 'and')
    if controllers:
        or_op = etree.SubElement(and_op, 'or')
        for controller_name in controllers:
            controller = etree.SubElement(or_op, 'labcontroller')
            controller.set('op', '=')
            controller.set('value', controller_name)

    system_type = etree.SubElement(host_requires, 'system_type')
    system_type.set("value", "Machine")
    and_op = etree.SubElement(host_requires, 'and')

    # Prepare requirements according to parameters
    requirements = []
    if params.arch:
        requirements.append("arch = " + params.arch)
    if params.min_mem:
        requirements.append("memory >= " + params.min_mem)
    if params.min_disk:
        requirements.append("DISKSPACE >= " + params.min_disk)
    if params.need_1g_hugepage:
        requirements.append("CPUFLAGS = pdpe1gb")
    if params.ndisk:
        requirements.append("NR_DISKS = " + params.ndisk)
    if params.need_hvm:
        requirements.append("HVM = 1")
    # hypervisor default as '' for bare metal
    requirements.append("hypervisor = " + params.hypervisor)
    if params.need_numa:
        requirements.append("numa_node_count >= 2")

    # Process CPU models filter
    cpu_models = []
    if params.need_westmere:
        cpu_models = ['47', '44', '37']
    elif params.need_cpu_models:
        cpu_models = params.need_cpu_models.split(',')

    if cpu_models:
        or_op = etree.SubElement(and_op, 'or')
        for model_name in cpu_models:
            cpu = etree.SubElement(or_op, 'cpu')
            model = etree.SubElement(cpu, 'model')
            model.set('op', '=')
            model.set('value', model_name)

    if params.need_cpu_vendor:
        vendor_name = params.need_cpu_vendor.lower()
        if 'intel' in vendor_name:
            cpu_vendor = 'GenuineIntel'
        elif 'amd' in vendor_name:
            # TODO: Fix vendor name 'AMD' for ARM could not be specified
            cpu_vendor = 'AuthenticAMD'
        elif 'ibm' in vendor_name:
            cpu_vendor = 'IBM'
        else:
            cpu_vendor = vendor_name

        or_op = etree.SubElement(and_op, 'or')
        cpu = etree.SubElement(or_op, 'cpu')
        vendor = etree.SubElement(cpu, 'vendor')
        vendor.set('op', '=')
        vendor.set('value', cpu_vendor)

    # Process required drivers
    device_drivers = []
    if params.need_device_drivers:
        device_drivers = params.need_drivers.split(',')
    elif params.need_sriov:
        device_drivers = ['igb', 'ixgbe', 'be2net', 'mlx4_core', 'enic']
    elif params.need_npiv:
        device_drivers = ['lpcf', 'qla2xxx']

    if device_drivers:
        or_op = etree.SubElement(and_op, 'or')
        for driver_name in device_drivers:
            device = etree.SubElement(or_op, 'device')
            driver = etree.SubElement(device, 'driver')
            driver.set('op', '=')
            driver.set('value', driver_name)

    # Translate requirements to beaker XML
    known_keys = ['arch', 'memory', 'numa_node_count', 'labcontroller', 'hypervisor']
    for requirement in requirements:
        try:
            key, op, value = requirement.split()
        except ValueError:
            key, op = requirement.split()
            value = ""
        if key in known_keys:
            require = etree.SubElement(and_op, key)
        else:
            require = etree.SubElement(and_op, 'key_value')
            require.set("key", key)
        require.set("op", op)
        require.set("value", value)


def fill_recipe(recipe, whiteboard, params):
    """
    Fill recipe element for beaker job XML according to parameters
    """
    recipe.set('whiteboard', whiteboard)
    recipe.set('role', 'None')
    recipe.set('ks_meta', "method=nfs harness='restraint-rhts staf'")
    recipe.set('kernel_options', "")

    if params.need_1g_hugepage:
        recipe.set("kernel_options_post",
                   "default_hugepagesz=1G hugepagesz=1G "
                   "hugepages=4 hugepagesz=2M hugepages=4")
    else:
        recipe.set('kernel_options_post', "")

    autopick = etree.SubElement(recipe, 'autopick')
    watchdog = etree.SubElement(recipe, 'watchdog')
    ks_appends = etree.SubElement(recipe, 'ks_appends')
    repos = etree.SubElement(recipe, 'repos')
    distro_requires = etree.SubElement(recipe, 'distroRequires')
    host_requires = etree.SubElement(recipe, 'hostRequires')
    packages = etree.SubElement(recipe, 'packages')

    autopick.set('random', 'false')
    if params.ignore_panic:
        watchdog.set('panic', 'ignore')

    fill_ks_appends(ks_appends, params)
    fill_packages(packages, params)
    fill_repos(repos, params)
    fill_distro_requires(distro_requires, params)
    fill_host_requires(host_requires, params)

    task = etree.SubElement(recipe, 'task')
    task.set('name', '/distribution/dummy')
    task.set('role', 'STANDALONE')
    task_params = etree.SubElement(task, 'params')
    task_param = etree.SubElement(task_params, 'param')
    task_param.set('name', 'RSTRNT_DISABLED')
    task_param.set('value', '01_dmesg_check 10_avc_check')

    task = etree.SubElement(recipe, 'task')
    task.set('name', '/distribution/reservesys')
    task.set('role', 'STANDALONE')
    task_params = etree.SubElement(task, 'params')
    task_param = etree.SubElement(task_params, 'param')
    task_param.set('name', 'RSTRNT_DISABLED')
    task_param.set('value', '01_dmesg_check 10_avc_check')
    task_param = etree.SubElement(task_params, 'param')
    task_param.set('name', 'RESERVETIME')
    task_param.set('value', str(int(params.reserve_days) * 86400))


def build_beaker_xml(params):
    """
    Build a beaker job XML file according to parameters
    """
    job = etree.Element('job')
    job.set('retention_tag', 'scratch')
    job.set('group', params.job_group)

    whiteboard_text = params.job_group
    if 'BUILD_URL' in os.environ:
        whiteboard_text += ' Jenkins URL: %s' % os.environ['BUILD_URL']
    whiteboard = etree.SubElement(job, 'whiteboard')
    whiteboard.text = whiteboard_text

    recipe_set = etree.SubElement(job, 'recipeSet')
    recipe_set.set('priority', 'Normal')

    recipe = etree.SubElement(recipe_set, 'recipe')
    fill_recipe(recipe, 'worker', params)
    if params.resource_host:
        resouce_recipe = etree.SubElement(recipe_set, 'recipe')
        fill_recipe(resouce_recipe, 'resource', params)

    ugly_xml = etree.tostring(job)
    pretty_xml = minidom.parseString(ugly_xml).toprettyxml(indent="  ")
    LOGGER.info("Beaker Job XML is:\n%s", pretty_xml)
    return pretty_xml


# pylint: disable=super-init-not-called,abstract-method
class BeakerAgent(BeakerCommand):
    def __init__(self, hub):
        self.hub = hub
        # pylint: disable=protected-access
        self.conf = hub._conf
        self.session = self.requests_session()

    def get_system_status(self, fqdn):
        status_url = 'systems/%s/status' % urllib.quote(fqdn, '')
        res = self.session.get(status_url)
        res.raise_for_status()
        return json.loads(res.text)

    def provision_system(self, fqdn, params):
        # Accept --distro for backwards compat
        # TODO: ks append?

        if not params.arch:
            raise Exception("Arch is not given")
        if not params.beaker_distro:
            raise Exception("Distro is not given")

        try:
            distro_tree = [
                dt for dt in self.hub.distrotrees.filter({
                    "name": params.beaker_distro,
                    "arch": params.arch,
                }) if dt['variant'] == "Server"
            ][0]
        except IndexError:
            LOGGER.info("Failed finding a distro with given name %s and arch %s, "
                        "wrong arch or distro name?",
                        params.beaker_distro, params.arch)

        LOGGER.info("Provisioning with distro tree %s", distro_tree['distro_name'])

        ks_meta = ("method=nfs harness='restraint-rhts staf'")

        kernel_options = ""
        if params.need_1g_hugepage:
            kernel_options_post = ("default_hugepagesz=1G hugepagesz=1G "
                                   "hugepages=4 hugepagesz=2M hugepages=4")
        else:
            kernel_options_post = ""

        self.hub.systems.provision(
            fqdn, distro_tree['distro_tree_id'],
            ks_meta, kernel_options, kernel_options_post,
            None,  # Kickstart is None
            True,  # Reboot
        )

        LOGGER.info("Reprovision issued, sleep for 3 min, wait for it to reboot..")
        time.sleep(60 * 3)


def get_beaker_hub():
    beaker_conf = "/etc/beaker/client.conf"
    try:
        conf = PyConfigParser()
        conf.load_from_file(beaker_conf)
    except IOError:
        LOGGER.error("Can't load beaker config file at %s", beaker_conf)
        LOGGER.error("Please install beaker-redhat for internal beaker workflow")
        sys.exit(1)

    try:
        LOGGER.info("Local beaker config loaded.")
        return HubProxy(conf=conf)
    except krbV.Krb5Error:
        LOGGER.info("No kerberos credentials cache, try to perform kinit")
        try:
            package.Package.from_name("krb5-workstation")
        except package.PackageNotExistsError:
            LOGGER.error("Package krb5-workstation is needed but not installed")
            sys.exit(1)
        user = getpass.getuser()
        if not utils.query_yes_no("Username {}, is that right?".format(user)):
            user = raw_input("Enter your username:")
        passwd = getpass.getpass(prompt="Kerberos Password:")
        p = subprocess.Popen(['kinit', '%s@REDHAT.COM' % user],
                             stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate(input=passwd)
        ret = p.wait()
        delattr(krbV, "_default_context")  # HACK: force reload context
        if err or ret:
            LOGGER.info("Failed with: %s", out)
        return HubProxy(conf=conf)


def reserve_beaker_systems(job_xml, hub):
    """
    Reserve beaker system according to job XML file
    """
    def _sigterm_handler(_signo, _):
        sys.exit(0)
    signal.signal(signal.SIGTERM, _sigterm_handler)
    done = False
    while not done:
        task_id = hub.jobs.upload(job_xml)
        task_url = "https://beaker.engineering.redhat.com/jobs/" + task_id[2:]
        LOGGER.info("Submitted beaker job %s", task_url)

        attempt = 0
        try:
            while not done:
                active_job_xml = etree.fromstring(
                    hub.taskactions.to_xml(task_id))
                LOGGER.info("Checking status of job %s (attempt %s)",
                            task_url, attempt)
                recipes = {}
                for recipe in active_job_xml.xpath('//recipe'):
                    recipe_info = recipe.attrib
                    recipes[recipe_info['id']] = dict(recipe_info)
                    LOGGER.info("Recipe %s: (system = %s) (status = %s) "
                                "(result = %s)",
                                recipe_info['id'],
                                recipe_info.get('system', 'queuing'),
                                recipe_info['status'],
                                recipe_info['result'])

                attempt += 1
                if all(info['status'] == 'Running' and info['result'] == 'Pass'
                       for info in recipes.values()):
                    LOGGER.info("Beaker job %s was successfully finished",
                                task_url)
                    done = True
                    return task_id, recipes
                if any(info['result'] in ['Warn', 'Fail', 'Panic']
                       for info in recipes.values()):
                    LOGGER.info("Beaker job %s failed. Resubmit job.",
                                task_url)
                    break
                if any(info['status'] in ['Aborted']
                       for info in recipes.values()):
                    LOGGER.info("Beaker job %s finished unexpectedly. "
                                "Resubmit job.", task_url)
                    break
                time.sleep(60)
        finally:
            if not done:
                msg = ("Provisioning aborted abnormally. "
                       "Canceling beaker job %s" % task_url)
                LOGGER.warning(msg)
                hub.taskactions.stop(task_id, 'cancel', msg)


def reprovisoin_beaker_systems(params):
    """
    Reprovision given machine
    Only works for machine managed by beaker
    """
    systems_reserve = []
    systems_reprovision = []

    LOGGER.info("Reprovisioning given machines: %s", params.target)
    for system in utils.split(params.target):
        LOGGER.info("Target machine is %s", system)
        hub = get_beaker_hub()

        user_name, _ = (
            krbV.default_context().default_ccache().principal().name.split("@"))

        agent = BeakerAgent(hub)

        try:
            system_status = agent.get_system_status(system)
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == 404:
                LOGGER.error("%s is not a machine managed by beaker!", system)
                return None

        status = system_status['condition']
        current_loan = system_status['current_loan']
        current_reservation = system_status['current_reservation']

        if current_loan:
            if current_loan.get('recipient_user').get('user_name') != user_name:
                LOGGER.error("%s is currently loaned by %s, can't continue, exiting...",
                             system, current_loan['user_name'])
                return None

        if current_reservation:
            if current_reservation['user_name'] != user_name:
                LOGGER.error("%s is currently reserved by %s, can't continue, exiting...",
                             system, current_reservation['user_name'])
                return None
            LOGGER.info("%s is reserved by you, reprovisioning...", system)
            systems_reprovision.append(system)
        elif status == "Automated":
            LOGGER.info("%s is an idle automated machine, submitting a job for it...")
            systems_reserve.append(system)
        else:
            LOGGER.info("%s not automated or reserved by you, can't continue.")
            return None

        for _system in systems_reserve:
            params.location = _system
            params.target = 'bkr'
            job_xml = build_beaker_xml(params)
            reserve_beaker_systems(job_xml, hub)

        for _system in systems_reprovision:
            agent.provision_system(_system, params)

        return systems_reserve + systems_reprovision
