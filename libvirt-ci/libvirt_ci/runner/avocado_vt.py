"""
Runner module for avocado-vt test framework
"""
import logging
import glob
import os
import re
import sys
import urllib
import urllib2

from .. import runner
from .. import utils
from .. import coverage

LOGGER = logging.getLogger(__name__)


def _clean_convert_with_pid():
    """
        Clean up qemu-img convert cmdline with pid
        Due to bug1510728
    """
    cmdline = "ps -ef | grep 'qemu-img convert' | grep -v 'grep'"
    psstdout = utils.run(cmdline, debug=True,).stdout
    if psstdout:
        cmdline = 'kill -9 %s' % psstdout.split()[1]
        utils.run(cmdline, debug=True,)


def _clear_residue_pid_files():
    """
    Clear up residue avocado-vt PID files. These files could be caused by
    a early termination of avocado process.
    """
    pid_files = glob.glob('/tmp/avocado-vt-joblock-*.pid')
    for pid_file in pid_files:
        with open(pid_file, 'r') as pid_fp:
            pid = pid_fp.read().strip()

        try:
            with open('/proc/%s/cmdline' % pid, 'r') as cmdline_fp:
                cmdline = cmdline_fp.read().split('\x00')
                if 'python' in cmdline[0]:
                    raise AvocadoVtRunnerError(
                        "Process %s (PID:%s) still running. "
                        "Abort testing" % (' '.join(cmdline), pid))
        except IOError:
            pass

        try:
            LOGGER.warning('Removing residue avocado-vt PID file %s',
                           pid_file)
            os.remove(pid_file)
        except IOError:
            pass


class AvocadoVtRunnerError(Exception):
    """
    Exception class for avocado-vt runner
    """
    pass


class AvocadoVtRunner(runner.RunnerBase):
    """
    Runner for avocado-vt test framework
    """
    repos = {
        'autotest':
            'https://github.com/libvirt-CI/autotest.git master',
        'tp-libvirt':
            'https://github.com/autotest/tp-libvirt.git master',
        'avocado':
            'https://github.com/avocado-framework/avocado.git 52lts',
        'avocado-vt':
            'https://github.com/avocado-framework/avocado-vt.git master',
    }
    main_vm = 'avocado-vt-vm1'
    required_packages = ['xz', 'fakeroot', 'python-sphinx', 'attr']
    default_nos = ['io-github-autotest-qemu']
    error_pattern = r'.*(ERROR)(.*)$'
    result_line_pattern = (
        r'(ERROR|INFO )\| (FAIL|ERROR|PASS|SKIP|CANCEL|WARN|TEST_NA) \S+\s+(.*)$')

    def init_coverage(self):
        """
        Test framework specific coverage initialization
        """
        cobertura_xml = None
        html_report_dir = None

        if os.environ.get('WORKSPACE'):
            if self.params.cobertura_xml:
                cobertura_xml = os.path.join(os.environ.get('WORKSPACE'),
                                             self.params.cobertura_xml)
            html_report_dir = os.path.join(os.environ.get('WORKSPACE'),
                                           'html_report')

        self.coverage = coverage.VirtcovCoverageHelper(cobertura_xml,
                                                       output_dir=html_report_dir)

    def init(self):
        """
        Test framework specific initialization.
        """
        if sys.version_info[1] == 6:
            self.required_packages += ['gmp-devel', 'xz-devel']

    def prepare_run(self):
        """
        Run specific preparation.
        """
        super(AvocadoVtRunner, self).prepare_run()
        self.restore_image()
        self.custom_prepare()

    def init_framework_params(self):
        """
        Initialize test framework specific parameters. These parameters are
        retrieved only after framework is prepared.
        Steps before framework preparation like `init, replace, bootstrap`
        **CANNOT** access these parameters
        """
        # pylint: disable=import-error,attribute-defined-outside-init
        from virttest import data_dir
        from virttest import defaults

        self.params.data_dir = data_dir.get_data_dir()
        self.params.tp_libvirt_dir = data_dir.get_test_provider_dir(
            'io-github-autotest-libvirt')

        default_guest = defaults.get_default_guest_os_info()
        self.params.default_guest_os = default_guest['variant']
        self.params.default_guest_asset = default_guest['asset']

        self.params.img_path = os.path.join(
            os.path.realpath(self.params.data_dir),
            'images/%s.qcow2' % self.params.default_guest_asset)

        # Workaround for NSS BZ#1317691 for v2v testing
        if self.params.vt_type == 'v2v':
            LOGGER.info('Setting up env variant for v2v')
            os.environ['NSS_STRICT_NOFORK'] = 'DISABLED'

    def replace(self):
        """
        Test framework specific file replaces.
        """
        vt_cfg = "etc/avocado/conf.d/vt.conf"
        base_cfg = "shared/cfg/base.cfg"
        linux_cfg = "shared/cfg/guest-os/Linux.cfg"
        img_cfg = "shared/cfg/guest-os/Linux/JeOS/*.x86_64.cfg"

        # Config avocado-vt to not backup/restore image to save testing time
        self.replace_pattern_in_file(
            vt_cfg,
            r'backup_image_before_test.*',
            'backup_image_before_test = False',
            repo='avocado-vt')
        self.replace_pattern_in_file(
            vt_cfg,
            r'restore_image_after_test.*',
            'restore_image_after_test = False',
            repo='avocado-vt')

        # Customize testing libvirt connect URI
        self.replace_pattern_in_file(
            vt_cfg,
            r'connect_uri.*',
            'connect_uri = %s' % self.params.connect_uri,
            repo='avocado-vt')

        # Customize testing main VM name
        if self.main_vm:
            self.replace_pattern_in_file(
                base_cfg,
                r'avocado-vt-vm1',
                self.main_vm,
                repo='avocado-vt')

        # Customize testing additional VM names
        if self.params.additional_vms and self.params.vt_type != 'v2v':
            vms_string = " ".join([self.main_vm] +
                                  utils.split(self.params.additional_vms))
            self.replace_pattern_in_file(
                base_cfg,
                r'^\s*vms = .*\n',
                r'vms = %s\n' % vms_string,
                repo='avocado-vt')

        # Customize guest password
        if self.params.password:
            self.replace_pattern_in_file(
                linux_cfg,
                r'password = \S*',
                r'password = %s' % self.params.password,
                repo='avocado-vt')

        # Customize guest OS variant
        if self.params.os_variant:
            self.replace_pattern_in_file(
                img_cfg,
                r'os_variant = \S*',
                r'os_variant = %s' % self.params.os_variant,
                repo='avocado-vt')

        # Workaround for test 'CANCEL' status not exist problem on 36lts
        if self.dist_major < 7:
            # FIXME: Not the right way to detect if this patch is needed or not
            # Should detect if the target branch is 36lts or not
            tp_libvirt_path = os.path.join(self.test_path, 'tp-libvirt')
            res = utils.run("grep -rl 'test.cancel' %s" % tp_libvirt_path)
            for _file in res.stdout.splitlines():
                self.replace_pattern_in_file(
                    _file,
                    r'test.cancel',
                    r'test.skip')

    def bootstrap(self):
        """
        Bootstrap this test framework.
        """
        avocado_path = os.path.join(self.test_path, 'avocado')
        avocado_vt_path = os.path.join(self.test_path, 'avocado-vt')
        tp_libvirt_path = os.path.join(self.test_path, 'tp-libvirt')
        autotest_path = os.path.join(self.test_path, 'autotest')
        utils.run_playbook('bootstrap_avocado_vt',
                           avocado_path=avocado_path,
                           avocado_vt_path=avocado_vt_path,
                           tp_libvirt_path=tp_libvirt_path,
                           autotest_path=autotest_path,
                           vt_type=self.params.vt_type)

    # pylint: disable=no-self-use
    def _split_name(self, name):
        """
        Try to return the module name of a test.
        """
        if name.startswith('type_specific.io-github-autotest-libvirt'):
            name = name.split('.', 2)[2]

        if name.split('.')[0] in ['virsh']:
            package_name, name = name.split('.', 1)
        else:
            package_name = ""

        names = name.split('.', 1)
        if len(names) == 2:
            name, test_name = names
        else:
            name = names[0]
            test_name = name
        if package_name:
            class_name = '.'.join((package_name, name))
        else:
            class_name = name

        return class_name, test_name

    def list_tests(self):
        """
        Get all specific type tests in avocado-vt.
        """
        cmd = 'avocado list --vt-type %s' % self.params.vt_type
        cmd += ' --vt-machine-type %s' % (self.params.vm_type or 'i440fx')
        if self.onlys:
            cmd += ' --vt-only-filter %s' % ','.join(self.onlys)
        LOGGER.info("Listing current test cases with '%s'", cmd)
        res = utils.run(cmd)
        out = res.stdout
        tests = []
        class_names = set()
        for line in out.splitlines():
            if re.match(r'VT\s+type_specific\.io-github-autotest-libvirt',
                        line):
                test = re.sub(
                    r'VT\s+type_specific\.io-github-autotest-libvirt'
                    r'\.(.*)', r'\1', line)
                if self.params.smoke:
                    class_name, _ = self._split_name(test)
                    if class_name in class_names:
                        continue
                    else:
                        class_names.add(class_name)
                tests.append(test)
        return tests

    def install_vm(self, img_path, **kwargs):
        """
        Install a customize VM
        """
        if 'lxc' in self.params.connect_uri:
            cmd = ('virt-install --connect %s --name %s --ram 500 '
                   '--noautoconsole' % (
                       self.params.connect_uri,
                       self.main_vm))
            res = utils.run(cmd)
            if res.exit_code:
                raise Exception('   ERROR: Failed to install guest\n%s' % res)
        else:
            cmd_template = (
                'virt-install --connect {uri} -n {vm_name} --hvm --accelerate '
                '-r {vm_ram} --vcpus={vm_vcpus} --os-variant {os_variant} '
                '--disk path={img_path},bus={disk_bus},format={img_format} '
                '--network {net_type}={net_name},model={net_model} '
                '--import --noreboot --noautoconsole --serial pty --debug')

            vm_name = kwargs.get('vm_name', self.main_vm)
            os_variant = kwargs.get('os_variant', self.params.os_variant)
            # Determain os_variant which could be recognized by virt-install
            # from VM name
            if os_variant == 'auto':
                os_variant = utils.determine_os_variant(vm_name)

            if self.dist_name == 'redhat' and int(self.dist_major) >= 7:
                if not os_variant.startswith("win"):
                    cmd_template += ' --memballoon model=virtio'

            if self.host_arch == 'aarch64':
                # aarch64 doesn't support PCI video device
                cmd_template += ' --graphics none --boot uefi'
            elif self.host_arch == 's390x':
                # s390x doesn't support PCI video device
                cmd_template += ' --graphics none'
            elif self.host_arch == 'ppc64le':
                cmd_template += ' --graphics vnc --video vga'
            else:
                cmd_template += ' --graphics vnc --video cirrus'

            uri = kwargs.get('uri', self.params.connect_uri)
            vm_ram = kwargs.get('vm_ram', 1024)
            vm_vcpus = kwargs.get('vm_vcpus', 2)
            disk_bus = kwargs.get('disk_bus', 'virtio')
            img_format = kwargs.get('img_format', 'qcow2')
            net_type = kwargs.get('net_type', 'bridge')
            net_name = kwargs.get('net_name', 'virbr0')
            net_model = kwargs.get('net_model', 'virtio')
            vm_type = kwargs.get('vm_type', 'i440fx')

            # A little trick here, since avocado recognize machine type as
            # i440fx, q35, but virt-install require a detailed and different name
            # on different arch.
            if vm_type:
                if vm_type == 'i440fx' and self.host_arch in ['x86_64', 'i386']:
                    cmd_template += ' --machine pc'
                elif vm_type == 'q35' and self.host_arch in ['x86_64', 'i386']:
                    cmd_template += ' --machine q35'
                else:
                    LOGGER.error("Unsupported vm_type %s on arch %s, fallback to default",
                                 vm_type, self.host_arch)

            cmd = cmd_template.format(
                uri=uri,
                vm_name=vm_name,
                vm_ram=vm_ram,
                vm_vcpus=vm_vcpus,
                os_variant=os_variant,
                img_path=img_path,
                disk_bus=disk_bus,
                img_format=img_format,
                net_type=net_type,
                net_name=net_name,
                net_model=net_model,
            )
            LOGGER.info("Refreshing all active pools before installing VM")
            pools_txt = utils.run(
                "virsh -c %s -q pool-list" % uri,
                debug=True).stdout
            pools = [line.split()[0] for line in pools_txt.splitlines()]
            for pool in pools:
                utils.run(
                    "virsh -c %s pool-refresh %s" % (uri, pool),
                    debug=True)
            LOGGER.info("Installing VM using command: \n%s", cmd)
            res = utils.run(cmd, debug=True)
            if res.exit_code:
                raise Exception('   ERROR: Failed to install guest\n%s' % res)

    def _prepare_v2v_vms(self, mount_src, mount_dest=None):
        """
        Mount and define VMs from a specific source where contains VM images.
        Only for v2v testing(convert local KVM VMs to oVirt).
        Note, calling this function after states.backup(), so both VMs and
        mount resource can be cleaned by states.check() automatically.
        """

        def _define_vm(xml):
            virsh_cmd = 'virsh'
            cmd_define = '%s define %s' % (virsh_cmd, xml)
            LOGGER.info('Define guest with command "%s"', cmd_define)
            return utils.run(cmd_define)

        if not self.params.v2v_vms_list:
            return
        os_variant_list = utils.split(self.params.v2v_vms_list)
        base_dir = '/var/lib/libvirt/images'
        if mount_dest is None:
            mount_dest = os.path.join(base_dir, 'v2v')
        LOGGER.info("Mount %s to %s and define VMs for v2v testing")
        if not os.path.exists(mount_dest):
            os.mkdir(mount_dest)
        utils.run('mount %s %s' % (mount_src, mount_dest))
        vm_xml_list = []
        for root, _, files in os.walk(mount_dest):
            if '.snapshot' not in root and 'lost+Found' not in root:
                for file_ in files:
                    if file_.endswith('.xml'):
                        vm_xml_list.append(os.path.join(root, file_))
        # For function job, define all vms available
        if self.params.v2v_vms_list == 'function':
            for xml in vm_xml_list:
                _define_vm(xml)
            return
        # Both arch and image format are fixed
        os_arch_list = ['i386', 'x86_64']
        img_format_list = ['', '-qcow2']
        # VM name: 'kvm-{os_variant}-{arch}-{image_format}'
        # VM image name: '{vm_name}.img'
        LOGGER.info('Installing v2v related VMs')
        vm_name_list = ['kvm-%s-%s%s' % (os_version, arch, fmt)
                        for os_version in os_variant_list
                        for arch in os_arch_list
                        for fmt in img_format_list]
        for vm_name in vm_name_list:
            exist = False
            virsh_cmd = 'virsh'
            if self.params.connect_uri:
                virsh_cmd += ' -c %s' % self.params.connect_uri
            vm_exist = utils.run('%s domstate %s' % (virsh_cmd, vm_name))
            if not vm_exist.exit_code:
                LOGGER.warning('Guest %s already exists', vm_name)
                continue
            for xml in vm_xml_list:
                if os.path.basename(xml) == vm_name + '.xml':
                    exist = True
                    cmd_result = _define_vm(xml)
                    if cmd_result.exit_code:
                        LOGGER.error('Failed to define guest %s', vm_name)
                    else:
                        LOGGER.info('Successfully defined %s', vm_name)
                    break
            if not exist:
                LOGGER.error('Not found xml file for guest %s', vm_name)

    def custom_prepare(self):
        """
        Customized preparation steps
        """
        def _remove_vms():
            LOGGER.info('Removing VMs')

            # Collect all possible conflicting VM names
            vm_names = set(['avocado-vt-vm1'])
            if self.main_vm:
                vm_names.add(self.main_vm)
            if self.params.additional_vms:
                vm_names.update(utils.split(self.params.additional_vms))

            # Clear them up all
            for vm_name in vm_names:
                utils.clean_vm(vm_name, self.params.connect_uri)

        def _prepare_network():
            LOGGER.info('Preparing network')
            if self.params.netxml:
                # Destroy network first
                utils.run("virsh -c %s net-destroy %s" %
                          (self.params.connect_uri, self.params.net_name))
                utils.run("virsh -c %s net-undefine %s" %
                          (self.params.connect_uri, self.params.net_name))
                netxml = self.params.netxml.format(
                    net_name=self.params.net_name)
                xml_path = '/tmp/test_net.xml'
                with open(xml_path, 'w') as xml_fp:
                    xml_fp.write(netxml)

                # Define and start new network
                res = utils.run("virsh -c %s net-define %s" %
                                (self.params.connect_uri, xml_path))
                if res.exit_code:
                    LOGGER.error('Net-define command result:\n%s', res)
                    raise Exception('Failed to define network for XML:\n%s' %
                                    netxml)
                res = utils.run("virsh -c %s net-start %s" %
                                (self.params.connect_uri,
                                 self.params.net_name))
                if res.exit_code:
                    LOGGER.error('Net-start command result:\n%s', res)
                    raise Exception('Failed to start network for XML:\n%s' %
                                    netxml)
                try:
                    os.remove(xml_path)
                except OSError:
                    pass

        def _install_vm():
            LOGGER.info('Installing VM')
            if self.params.domxml:
                if self.params.domxml.count("ISO_IMG"):
                    iso_img = "/tmp/test_img.iso"
                    utils.run("mkisofs -o /tmp/test_img.iso /root/*.*")
                    if not os.path.exists(iso_img):
                        raise Exception('Failed to create ISO image')
                    domxml = self.params.domxml.format(
                        name=self.main_vm, image_path=self.params.img_path,
                        ISO_IMG=iso_img)
                else:
                    domxml = self.params.domxml.format(
                        name=self.main_vm, image_path=self.params.img_path)

                xml_path = '/tmp/virt-test-ci.xml'
                with open(xml_path, 'w') as xml_fp:
                    xml_fp.write(domxml)
                res = utils.run("virsh -c %s define %s" %
                                (self.params.connect_uri, xml_path))
                if res.exit_code:
                    LOGGER.error('Define command result:\n%s', res)
                    raise Exception('Failed to define domain for XML:\n%s' %
                                    domxml)
                try:
                    os.remove(xml_path)
                except OSError:
                    pass
            else:
                self.install_vm(self.params.img_path, vm_type=self.params.vm_type)

        def _install_additional_vms():
            if self.params.additional_vms:
                LOGGER.info('Installing additional VMs')
                for vm_name in utils.split(self.params.additional_vms):
                    cmd = 'virt-clone '
                    if self.params.connect_uri:
                        cmd += '--connect=%s ' % self.params.connect_uri
                    cmd += '--original=%s ' % self.main_vm
                    cmd += '--name=%s ' % vm_name
                    cmd += '--auto-clone'
                    utils.run(cmd)

        if self.params.retain_vm:
            return

        _remove_vms()
        _prepare_network()
        _install_vm()
        _install_additional_vms()

        if self.params.vt_type == 'v2v' and self.params.screenshots_url:
            screenshots_path = os.path.join(
                os.path.realpath(self.params.data_dir), 'screenshots')
            if not os.path.exists(screenshots_path):
                os.mkdir(screenshots_path)
            screenshots = urllib2.urlopen(self.params.screenshots_url).read()
            screenshot_list = re.findall(r'>(win.+.ppm)<', screenshots)
            for sshot in screenshot_list:
                retrieve_url = urllib.basejoin(self.params.screenshots_url,
                                               sshot)
                dest_path = os.path.join(screenshots_path, sshot)
                LOGGER.info("Downloading windows screenshots from %s to %s",
                            retrieve_url, dest_path)
                urllib.urlretrieve(retrieve_url, dest_path)

        # Install VMs for v2v testing
        if self.params.vt_type == 'v2v' and self.params.v2v_vms_src:
            self._prepare_v2v_vms(self.params.v2v_vms_src)

    def run_test(self, test_name):
        """
        Run a single test
        """
        cmd = ('python -u `which avocado` run --vt-type %s '
               '--vt-machine-type %s %s'
               % (self.params.vt_type, self.params.vm_type or 'i440fx', test_name))
        if self.params.connect_uri:
            cmd += ' --vt-connect-uri %s' % self.params.connect_uri
        return utils.run(cmd, timeout=int(self.params.timeout))

    # pylint: disable=no-self-use
    def parse_result(self, result):
        """
        Parse result into variables loggable.
        """
        def _split_log(log_txt):
            """
            Split up logs
            """
            logs = []
            cur_line = ''
            for line in log_txt.splitlines():
                patt = r'.*(ERROR|INFO |WARNI|DEBUG)\|.*'
                if re.match(patt, line):
                    logs.append(cur_line)
                    cur_line = line
                else:
                    cur_line += line
            if cur_line:
                logs.append(cur_line)
            return logs

        lines = result.stdout.splitlines()
        log_file = ''
        status = 'INVALID'
        for line in lines:
            if re.match(r' ?\(1/1\)', line):
                try:
                    status = line.split()[2]
                except IndexError:
                    pass
            if re.match(r'(JOB|DEBUG) LOG', line):
                log_file = line.split()[-1]

        if status == "INVALID" and result.exit_status != 'timeout':
            return (status, result.stdout.splitlines())

        if not log_file:
            LOGGER.error('Log file not found in result:\n%s', result)
            return status, []

        LOGGER.debug('Log file found in "%s"', log_file)
        try:
            with open(log_file) as log_fp:
                log_txt = log_fp.read()
        except (IOError, OSError) as detail:
            LOGGER.error("Unable to read log file %s:\n%s",
                         log_file, detail)
        return status, _split_log(log_txt)

    def prepare_test(self, _):
        """
        Action to perform before a test case
        """
        _clean_convert_with_pid()

        utils.clean_vm_with_pid(self.main_vm, self.host)

        res = utils.run("virsh -c %s dumpxml %s" %
                        (self.params.connect_uri, self.main_vm))
        if not res.exit_code:
            domxml = res.stdout
            fname = ('/var/lib/libvirt/qemu/nvram/%s_VARS.fd' %
                     self.main_vm)
            if not os.path.exists(fname) and fname in domxml:
                LOGGER.warning('Removing nvram line...')
                domxml = re.sub('<nvram>.*</nvram>', '', domxml)
                utils.clean_vm(self.main_vm, self.params.connect_uri)

                xml_path = '/tmp/virt-test-ci.xml'
                with open(xml_path, 'w') as xml_fp:
                    xml_fp.write(domxml)
                res = utils.run("virsh -c %s define %s" %
                                (self.params.connect_uri, xml_path))
                if res.exit_code:
                    LOGGER.error('Define command result:\n%s', res)
                    raise Exception('Failed to define domain for XML:\n%s' %
                                    domxml)
                try:
                    os.remove(xml_path)
                except OSError:
                    pass
        else:
            LOGGER.warning('Failed to dumpxml from %s\n%s',
                           self.main_vm, res)
        _clear_residue_pid_files()

    def update_report(self, test, status, result_line, duration, logs, _idx):
        """
        Update test report according to result data
        """
        if (
                ('LoginTimeoutError' in result_line or
                 'Cannot access storage file' in result_line or
                 'Fail to get information of' in result_line) and
                status != "PASS" and
                'virsh.migrate' in test
        ):
            LOGGER.warn("Failed migration job may break the image, "
                        "trying to restore the image.")
            self.restore_image()

        class_name, test_name = self._split_name(test)
        status, result_line = self._ignore_failures(
            test_name, status, result_line)
        self.report.update(test_name, class_name, status, '\n'.join(logs),
                           result_line, duration,
                           prefix=self.params.qemu_pkg)

    # pylint:disable=arguments-differ
    def check_need_rerun(self, result):
        """
        Check if one test need rerun
        """
        need_rerun = False
        reason = None
        meta_corrupt = 'Metadata corruption detected'
        image_corrupt = 'Leaked clusters were noticed during image check'
        ppc_corrupt = 'Setup DoneLinux ppc64le'
        corrupt_info = [meta_corrupt, image_corrupt, ppc_corrupt]
        if result['status'] in ['FAIL', 'ERROR', 'TIMEOUT', 'INVALID']:
            for corrupt in corrupt_info:
                if any(corrupt in log for log in result['logs']):
                    need_rerun = True
                    reason = 'Image corruption: %s' % corrupt
                    self.restore_image()
                    break
        return need_rerun, reason


class AvocadoVtRemoteRunner(AvocadoVtRunner):
    """
    Remote Runner for avocado-vt test framework
    """

    def init(self):
        """
        Test framework specific initialization.
        """
        self.host = self.params.host
        self.pip_option = self.params.pip_option
        self.xz_img_path = self.params.img_url
        self.private_key = 'libvirt-jenkins'

        # Create venv path
        cmd = "mktemp -d -p ~/ -t .libvirt-ci-venv-avocado-remote-XXXXXX"
        result = utils.run(cmd, host=self.host, debug=True, ignore_fail=False)
        self.venv_path = result.stdout.splitlines()[0].strip()

    def init_framework_params(self):
        """
        Initialize test framework specific parameters. These parameters are
        retrieved only after framework is prepared.
        Steps before framework preparation like `init, replace, bootstrap`
        **CANNOT** access these parameters
        """
        pass

    def prepare_image(self):
        """
        Prepare test image file
        """
        pass

    def restore_image(self):
        """
        Restore test image file
        """
        utils.run_playbook('restore_image_remote',
                           hosts=self.host,
                           private_key=self.private_key,
                           debug=True,
                           remote=self.host)

    def backup_image(self):
        """
        Backup test image file
        """
        pass

    def prepare_packages(self):
        """
        Prepare packages
        """
        cmd = 'yum -y remove \\*-rhev'
        utils.run(cmd, host=self.host, debug=True, ignore_fail=False)

    def prepare_run(self):
        """
        Run specific preparation.
        """
        self.init_params()

    def prepare_test(self, _):
        """
        Action to perform before a test case
        """
        pass

    def list_tests(self):
        """
        Get all specific type tests in avocado-vt.
        """
        options = '--vt-type %s' % self.params.vt_type
        options += ' --vt-machine-type %s' % (self.params.vm_type or 'i440fx')
        if self.onlys:
            options += ' --vt-only-filter %s' % ','.join(self.onlys)
        LOGGER.info("Listing current test cases with '%s'", options)
        res = utils.run_playbook('avocado_cmd',
                                 hosts=self.host,
                                 debug=True,
                                 private_key=self.private_key,
                                 remote=self.host,
                                 venv_path=self.venv_path,
                                 avocado_cmd='list',
                                 options=options,
                                 timeout=120)

        tests = []
        class_names = set()
        for line in res.stdout_lines:
            if re.match(r'VT\s+type_specific\.io-github-autotest-libvirt',
                        line):
                test = re.sub(
                    r'VT\s+type_specific\.io-github-autotest-libvirt'
                    r'\.(.*)', r'\1', line)
                if self.params.smoke:
                    class_name, _ = self._split_name(test)
                    if class_name in class_names:
                        continue
                    else:
                        class_names.add(class_name)
                tests.append(test)
        return tests

    def fetch_file(self, file_path):
        """
        Fetch file to local
        """
        dir_path = os.path.dirname(file_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        dir_path += '/'
        utils.run_playbook("fetch_file",
                           hosts=self.host,
                           private_key=self.private_key,
                           remote=self.host,
                           file_path=file_path,
                           dir_path=dir_path)

    def run_test(self, test_name):
        """
        Run a single test
        """
        log_file = ''
        options = ('--vt-type %s --vt-machine-type %s %s' %
                   (self.params.vt_type,
                    self.params.vm_type or 'i440fx',
                    test_name))
        if self.params.connect_uri:
            options += ' --vt-connect-uri %s' % self.params.connect_uri
        res = utils.run_playbook('avocado_cmd',
                                 hosts=self.host,
                                 private_key=self.private_key,
                                 ignore_fail=True,
                                 remote=self.host,
                                 venv_path=self.venv_path,
                                 avocado_cmd='run',
                                 options=options,
                                 timeout=int(self.params.timeout))

        for line in res.stdout_lines:
            if re.match(r'(JOB|DEBUG) LOG', line):
                log_file = line.split()[-1]

        if log_file:
            LOGGER.debug("Copy the log file to local")
            self.fetch_file(log_file)

        return res

    def bootstrap(self):
        """
        Bootstrap this test framework.
        """
        extra_vars = {'remote': self.host}
        extra_vars['pip_option'] = self.pip_option
        extra_vars['img_path'] = self.xz_img_path
        extra_vars['venv_path'] = self.venv_path
        extra_vars['test_path'] = self.test_path
        extra_vars['vt_type'] = self.params.vt_type
        qemu_package = 'qemu-kvm-rhev'
        if self.params.qemu_pkg == 'rhel':
            qemu_package = 'qemu-kvm-ma'
        extra_vars['qemu_pkg'] = qemu_package
        if self.params.domxml:
            extra_vars['domxml'] = self.params.domxml
        if self.params.additional_vms:
            extra_vars['extra_vms'] = utils.split(self.params.additional_vms)
        utils.run_playbook('bootstrap_avocado_vt_remote',
                           hosts=self.host,
                           private_key=self.private_key,
                           **extra_vars)
