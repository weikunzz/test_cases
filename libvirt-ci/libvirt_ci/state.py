import logging
import re
import os
import difflib
import tempfile
import traceback
import shutil
import copy
import collections

from . import utils

LOGGER = logging.getLogger(__name__)


def encapsulate_states():
    """
    Encapsulate all kinds of States orderly
    """
    states = {}
    ordered_states = collections.OrderedDict()

    for cls in utils.all_leaf_class(State):
        states[cls.__name__] = cls()

    def dependency_update(name, obj):
        depend_states = copy.copy(obj.depend_states)
        for depend_state in depend_states:
            if depend_state in states:
                dependency_update(depend_state, states[depend_state])
            else:
                LOGGER.warning("'%s' does not exist", depend_state)
        if name not in ordered_states.keys():
            ordered_states[name] = obj

    for state_name, state_obj in states.items():
        dependency_update(state_name, state_obj)

    return ordered_states.values()


class States(object):

    def __init__(self, host=None):
        self.states = encapsulate_states()
        self.host = host
        dist_vendor, dist_major, _, _ = utils.get_dist(host=self.host)
        blacked_state = []
        if dist_vendor == 'redhat' and dist_major < 7:
            blacked_state = ['LIOFileioState', 'LIOISCSIState']
        if ((dist_vendor == 'redhat' and dist_major > 6) or
                dist_vendor == 'fedora'):
            blacked_state = ['TgtState']
        for state in self.states:
            state.dist_vendor = dist_vendor
            state.dist_major = dist_major
            if type(state).__name__ in blacked_state:
                self.states.remove(state)
                del state

    def backup(self):
        for state in self.states:
            if self.host:
                state.host = self.host
            state.backup()

    def check(self, recover=True):
        msg = []
        for state in self.states:
            msg += state.check(recover=recover)
        return msg


class State(object):
    name = None
    permit_keys = []
    permit_re = []
    permit_names = []
    depend_states = []

    def __init__(self):
        self.current_state = None
        self.backup_state = None
        self.host = None
        self.dist_vendor = 'Unknown'
        self.dist_major = -1

    def get_names(self):
        raise NotImplementedError('Function get_names not implemented for %s.'
                                  % self.__class__.__name__)

    def get_info(self, name):
        raise NotImplementedError('Function get_info not implemented for %s.'
                                  % self.__class__.__name__)

    def remove(self, name):
        raise NotImplementedError('Function remove not implemented for %s.'
                                  % self.__class__.__name__)

    def restore(self, name):
        raise NotImplementedError('Function restore not implemented for %s.'
                                  % self.__class__.__name__)

    def get_state(self):
        names = self.get_names()
        state = {}
        for name in names:
            state[name] = self.get_info(name)
        return state

    def backup(self):
        """
        Backup current state
        """
        self.backup_state = self.get_state()

    def check(self, recover=False):
        """
        Check state changes and recover to specified state.
        Return a result.
        """
        def lines_permissible(diff, permit_re):
            """
            Check whether the diff message is in permissible list of regexs.
            """
            diff_lines = set()
            for line in diff[2:]:
                if re.match(r'^[-+].*', line):
                    diff_lines.add(line)

            for line in diff_lines:
                permit = False
                for r in permit_re:
                    if re.match(r, line):
                        permit = True
                        break
                if not permit:
                    return False
            return True

        self.current_state = self.get_state()
        diff_msg = []
        new_items, del_items, unchanged_items = utils.diff_dict(
            self.backup_state, self.current_state)
        # Don't check permissible items
        new_items = new_items - set(self.permit_names)
        del_items = del_items - set(self.permit_names)
        unchanged_items = unchanged_items - set(self.permit_names)
        if new_items:
            diff_msg.append('Created %s(s):' % self.name)
            for item in new_items:
                diff_msg.append(item)
                if recover:
                    try:
                        self.remove(self.current_state[item])
                    # pylint: disable=broad-except
                    except Exception as e:
                        traceback.print_exc()
                        diff_msg.append('Remove failed:\n %s' % e)

        if del_items:
            diff_msg.append('Deleted %s(s):' % self.name)
            for item in del_items:
                diff_msg.append(item)
                if recover:
                    try:
                        self.restore(item)
                    # pylint: disable=broad-except
                    except Exception as e:
                        traceback.print_exc()
                        diff_msg.append('Recover failed:\n %s' % e)

        for item in unchanged_items:
            cur = self.current_state[item]
            bak = self.backup_state[item]
            item_changed = False
            new_keys, del_keys, unchanged_keys = utils.diff_dict(bak, cur)
            if new_keys:
                item_changed = True
                diff_msg.append('Created key(s) in %s %s:' % (self.name, item))
                for key in new_keys:
                    diff_msg.append(key)
            if del_keys:
                for key in del_keys:
                    if type(key) in (str, unicode):
                        if key not in self.permit_keys:
                            item_changed = True
                            diff_msg.append('Deleted key(s) in %s %s:' %
                                            (self.name, item))
                        else:
                            LOGGER.warning("Deleted key '%s' is permissible, "
                                           "Won't restore", key)
                    else:
                        item_changed = True
                        diff_msg.append('Deleted key(s) in %s %s:' %
                                        (self.name, item))
            for key in unchanged_keys:
                if type(cur[key]) in (str, unicode):
                    if cur[key] != bak[key]:
                        if key not in self.permit_keys:
                            item_changed = True
                            diff_msg.append('%s %s: %s changed: %s -> %s' % (
                                self.name, item, key, bak[key], cur[key]))
                        else:
                            LOGGER.warning(
                                "Changed key '%s'(%s -> %s) is permissible, "
                                "Won't restore", key, bak[key], cur[key])
                elif type(cur[key]) is list:
                    diff = difflib.unified_diff(
                        bak[key], cur[key], lineterm="")
                    tmp_msg = []
                    for line in diff:
                        tmp_msg.append(line)
                    if tmp_msg and not lines_permissible(tmp_msg,
                                                         self.permit_re):
                        item_changed = True
                        diff_msg.append('%s %s: "%s" changed:' %
                                        (self.name, item, key))
                        show_length = 20
                        if len(tmp_msg) > show_length:
                            diff_msg += tmp_msg[:show_length]
                            diff_msg.append('< %s lines not shown >' %
                                            (len(tmp_msg) - show_length))
                        else:
                            diff_msg += tmp_msg
                        diff_msg += tmp_msg
                elif isinstance(cur[key], dict):
                    new_keys, del_keys, unchanged_keys = utils.diff_dict(
                        bak[key], cur[key])
                    if new_keys:
                        item_changed = True
                        diff_msg.append(
                            'Created key(s) in %s %s:' % (self.name,
                                                          unchanged_keys))
                        for _key in new_keys:
                            diff_msg.append(_key)
                    if del_keys:
                        item_changed = True
                        diff_msg.append('Deleted key(s) in %s %s:' %
                                        (self.name, unchanged_keys))
                else:
                    diff_msg.append('%s %s: %s: Invalid type %s.' % (
                        self.name, item, key, type(cur[key])))
            if item_changed and recover:
                try:
                    self.restore(item)
                # pylint: disable=broad-except
                except Exception as err:
                    traceback.print_exc()
                    diff_msg.append('Recover is failed:\n %s' % err)
        return diff_msg

    def temp_file(self, content):
        """
        Create temp file and write the content.
        Copy the file to remote if host is not None
        :param content: content str
        :return: the file path
        """
        tmp_file = tempfile.NamedTemporaryFile(delete=False)
        fname = tmp_file.name
        tmp_file.writelines(content)
        tmp_file.close()
        if self.host:
            utils.run_playbook('copy_file',
                               hosts=self.host,
                               private_key='libvirt-jenkins',
                               ignore_fail=True,
                               remote=self.host,
                               file_path=fname)
        return fname


class DomainState(State):
    name = 'domain'
    permit_keys = ['id', 'cpu time', 'security label']
    depend_states = ['ServiceState']

    def remove(self, name):
        dom = name
        utils.clean_vm(dom['name'], host=self.host)

    def restore(self, name):
        dom = self.backup_state[name]
        name = dom['name']
        doms = self.current_state
        if name in doms:
            self.remove(doms[name])
        else:
            utils.clean_vm_with_pid(name, host=self.host)

        fname = self.temp_file(dom['inactive xml'])

        try:
            if dom['persistent'] == 'yes':
                res = utils.run("virsh define %s" % fname, host=self.host)
                if res.exit_code:
                    raise Exception(str(res))
                if dom['state'] != 'shut off':
                    res = utils.run("virsh start %s" % name, host=self.host)
                    if res.exit_code:
                        raise Exception(str(res))
            else:
                res = utils.run("virsh create %s" % fname, host=self.host)
                if res.exit_code:
                    raise Exception(str(res))
        finally:
            os.remove(fname)

        if dom['autostart'] == 'enable':
            res = utils.run("virsh autostart %s" % name, host=self.host)
            if res.exit_code:
                raise Exception(str(res))

        if dom['managed save'] == 'no':
            res = utils.run('virsh managedsave-remove %s' % name,
                            host=self.host)
            if res.exit_code:
                raise Exception(str(res))

    def get_info(self, name):
        infos = {}
        for line in utils.run("virsh dominfo %s" % name,
                              host=self.host).stdout.strip().splitlines():
            key, value = line.split(':', 1)
            infos[key.lower()] = value.strip()
        infos['inactive xml'] = utils.run(
            "virsh dumpxml %s --inactive" % name,
            host=self.host).stdout.splitlines()
        return infos

    def get_names(self):
        return utils.run("virsh list --all --name",
                         host=self.host).stdout.splitlines()


class NetworkState(State):
    name = 'network'
    depend_states = ['ServiceState']

    def remove(self, name):
        """
        Remove target network _net_.

        :param net: Target net to be removed.
        """
        net = name
        if net['active'] == 'yes':
            res = utils.run("virsh net-destroy %s" % net['name'],
                            host=self.host)
            if res.exit_code:
                raise Exception(str(res))
        if net['persistent'] == 'yes':
            res = utils.run("virsh net-undefine %s" % net['name'],
                            host=self.host)
            if res.exit_code:
                raise Exception(str(res))

    def restore(self, name):
        """
        Restore networks from _net_.

        :param net: Target net to be restored.
        :raise CalledProcessError: when restore failed.
        """
        net = self.backup_state[name]
        name = net['name']
        nets = self.current_state
        if name in nets:
            self.remove(nets[name])

        fname = self.temp_file(net['inactive xml'])

        try:
            if net['persistent'] == 'yes':
                res = utils.run("virsh net-define %s" % fname, host=self.host)
                if res.exit_code:
                    raise Exception(str(res))
                if net['active'] == 'yes':
                    res = utils.run("virsh net-start %s" % name,
                                    host=self.host)
                    if res.exit_code:
                        res = utils.run("virsh net-start %s" % name,
                                        host=self.host)
                        if res.exit_code:
                            raise Exception(str(res))
            else:
                res = utils.run("virsh net-create %s" % fname,
                                host=self.host)
                if res.exit_code:
                    raise Exception(str(res))
        finally:
            os.remove(fname)

        if net['autostart'] == 'yes':
            res = utils.run("virsh net-autostart %s" % name,
                            host=self.host)
            if res.exit_code:
                raise Exception(str(res))

    def get_info(self, name):
        infos = {}
        for line in utils.run(
                "virsh net-info %s" % name,
                host=self.host).stdout.strip().splitlines():
            key, value = line.split()
            if key.endswith(':'):
                key = key[:-1]
            infos[key.lower()] = value.strip()
        cmd = "virsh net-dumpxml --inactive %s" % name
        infos['inactive xml'] = utils.run(cmd,
                                          host=self.host).stdout.splitlines()
        return infos

    def get_names(self):
        lines = utils.run(
            "virsh net-list --all",
            host=self.host).stdout.strip().splitlines()[2:]
        return [line.split()[0] for line in lines]


class PoolState(State):
    name = 'pool'
    permit_keys = ['available', 'allocation']
    permit_re = [r'^[-+]\s*\<(capacity|allocation|available).*$']
    permit_names = ['images']
    depend_states = ['ServiceState']

    def remove(self, name):
        """
        Remove target pool _pool_.

        :param pool: Target pool to be removed.
        """
        pool = name
        if pool['state'] == 'running':
            res = utils.run("virsh pool-destroy %s" % pool['name'],
                            host=self.host)
            if res.exit_code:
                raise Exception(str(res))
        if pool['persistent'] == 'yes':
            res = utils.run("virsh pool-undefine %s" % pool['name'],
                            host=self.host)
            if res.exit_code:
                LOGGER.error(res.stderr)
                # This is a workaround for BZ#1242801
                tmp_xml = '/tmp/bz1242801pool.xml'
                cmd = "virsh pool-dumpxml %s > %s" % (pool['name'], tmp_xml)
                utils.run(cmd, host=self.host)
                utils.run("virsh pool-define %s" % tmp_xml, host=self.host)
                utils.run("virsh pool-undefine %s" % pool['name'],
                          host=self.host)
                os.unlink(tmp_xml)
                res = utils.run("virsh pool-list --all|grep %s" % pool['name'],
                                host=self.host)
                if res.exit_code:
                    raise Exception("Can't delete pool %s" % pool['name'])

    def restore(self, name):
        pool = self.backup_state[name]
        name = pool['name']
        pools = self.current_state
        if name in pools:
            self.remove(pools[name])

        fname = self.temp_file(pool['inactive xml'])

        try:
            if pool['persistent'] == 'yes':
                res = utils.run("virsh pool-define %s" % fname, host=self.host)
                if res.exit_code:
                    raise Exception(str(res))
                if pool['state'] == 'running':
                    res = utils.run("virsh pool-start %s" % name,
                                    host=self.host)
                    if res.exit_code:
                        raise Exception(str(res))
            else:
                res = utils.run("virsh pool-create %s" % fname, host=self.host)
                if res.exit_code:
                    raise Exception(str(res))
        finally:
            os.remove(fname)

        if pool['autostart'] == 'yes':
            res = utils.run("virsh pool-autostart %s" % name, host=self.host)
            if res.exit_code:
                raise Exception(str(res))

    def get_info(self, name):
        infos = {}
        for line in utils.run(
                "virsh pool-info %s" % name,
                host=self.host).stdout.strip().splitlines():
            key, value = line.split(':', 1)
            infos[key.lower()] = value.strip()
        infos['inactive xml'] = utils.run(
            "virsh pool-dumpxml --inactive %s" % name,
            host=self.host).stdout.splitlines()
        infos['volumes'] = utils.run(
            "virsh vol-list %s" % name,
            host=self.host).stdout.strip().splitlines()[2:]
        return infos

    def get_names(self):
        lines = utils.run(
            "virsh pool-list --all",
            host=self.host).stdout.strip().splitlines()[2:]
        return [line.split()[0] for line in lines]


class SecretState(State):
    name = 'secret'
    permit_keys = []
    permit_re = []
    depend_states = ['ServiceState']

    def remove(self, name):
        secret = name
        res = utils.run("virsh secret-undefine %s" % secret['uuid'],
                        host=self.host)
        if res.exit_code:
            raise Exception(str(res))

    def restore(self, name):
        name = uuid = self.backup_state[name]
        cur = self.current_state
        bak = self.backup_state

        if uuid in cur:
            self.remove(name)

        fname = self.temp_file(bak[name]['xml'])

        try:
            res = utils.run("virsh secret-define %s" % fname, host=self.host)
            if res.exit_code:
                raise Exception(str(res))
        finally:
            os.remove(fname)

    def get_info(self, name):
        infos = {}
        infos['uuid'] = name
        infos['xml'] = utils.run("virsh secret-dumpxml %s" % name,
                                 host=self.host).stdout.splitlines()
        return infos

    def get_names(self):
        lines = utils.run("virsh secret-list",
                          host=self.host).stdout.strip().splitlines()[2:]
        return [line.split()[0] for line in lines]


class MountState(State):
    name = 'mount'
    permit_keys = []
    permit_re = []
    info = {}
    depend_states = ['ServiceState']

    def remove(self, name):
        info = name
        res = utils.run("umount %s" % info['mount_point'], host=self.host)
        if res.exit_code:
            raise Exception("Failed to unmount %s:%s" %
                            (info['mount_point'], res.stderr))

    def restore(self, name):
        info = self.backup_state[name]
        # User mount point is not recoverable
        if info['mount_point'].startswith('/run/user'):
            return
        cmd = "mount -t %s %s %s" % (info['fstype'],
                                     info['src'], info['mount_point'])
        res = utils.run(cmd, host=self.host)
        if res.exit_code:
            raise Exception("Failed to mount %s:%s" %
                            (info['mount_point'], res.stderr))

    def get_info(self, name):
        return self.info[name]

    def get_names(self):
        """
        Get all mount infomations from /etc/mtab.

        :return: A dict using mount point as keys and 6-element dict as value.
        """
        if not self.host:
            lines = file('/etc/mtab').read().splitlines()
        else:
            ret = utils.run('cat /etc/mtab', host=self.host)
            lines = ret.stdout_lines
        names = []
        for line in lines:
            if 'binfmt_misc' in line:
                LOGGER.debug("Skip check with binfmt_misc mount: %s", line)
                continue
            values = line.split()
            if len(values) != 6:
                LOGGER.warning('Error parsing mountpoint: %s', line)
                continue
            keys = ['src', 'mount_point', 'fstype', 'options', 'dump', 'order']
            mount_entry = dict(zip(keys, values))
            mount_point = mount_entry['mount_point']
            names.append(mount_point)
            self.info[mount_point] = mount_entry
        return names


class ExportfsState(State):
    name = 'export list'
    info = {}
    depend_states = ['MountState']

    def remove(self, name):
        info = name
        if info['export_addr'] == 'world':
            export_addr = '*'
        cmd = 'exportfs -u %s:%s' % (export_addr, info['export_dir'])
        res = utils.run(cmd, host=self.host)
        if res.exit_code:
            raise Exception(res.stderr)

    def restore(self, name):
        # No need to recover tmp export dir
        pass

    def get_info(self, name):
        return self.info[name]

    def get_names(self):
        names = []
        export_list = utils.run('exportfs -v',
                                host=self.host).stdout.splitlines()
        patt = re.compile(r'(\S+)\s+<?(\S+?)>?\((\S+)\)')
        keys = ['export_dir', 'export_addr', 'export_opt']
        for item in export_list:
            if patt.match(item):
                record = dict(zip(keys, patt.match(item).groups()))
                export_dir = record['export_dir']
                names.append(export_dir)
                self.info[export_dir] = record
        return names


class ServiceState(State):
    name = 'service'
    permit_keys = []
    permit_re = []
    depend_states = []

    def remove(self, name):
        raise Exception('It is meaningless to remove service %s' % name)

    def restore(self, name):
        name = info = self.backup_state[name]
        if info['name'] == 'selinux':
            utils.run('setenforce %s' % info['status'], host=self.host)
        else:
            if info['status'] == 'running':
                utils.run("service %s start" % info['name'], host=self.host)
            elif info['status'] == 'stopped':
                utils.run("service %s stop" % info['name'], host=self.host)
            else:
                raise Exception("Unknown status %s" % info['status'])

    def get_info(self, name):
        if name == 'selinux':
            status = utils.run('getenforce', host=self.host).stdout.strip()
        else:
            if utils.run("service %s status" % name,
                         host=self.host).exit_code == 0:
                status = 'running'
            else:
                status = 'stopped'
        return {'name': name, 'status': status}

    def get_names(self):
        s_list = ['libvirtd', 'selinux', 'nfs', 'iscsid', 'tgtd']
        if ((self.dist_vendor == 'redhat' and self.dist_major > 6) or
                self.dist_vendor == 'fedora'):
            s_list.remove('tgtd')
        return s_list


class DirState(State):
    name = 'directory'
    permit_keys = ['aexpect', 'address_pool', 'address_pool.lock']
    depend_states = ['ServiceState']

    def remove(self, name):
        raise Exception('It is not wise to remove a dir %s' % name)

    def restore(self, name):
        name = self.backup_state[name]
        dirname = name['dir-name']
        cur = self.current_state[dirname]
        bak = self.backup_state[dirname]
        created_files = set(cur) - set(bak) - set(self.permit_keys)
        if created_files:
            for fname in created_files:
                fpath = os.path.join(name['dir-name'], fname)
                if not self.host:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                    elif os.path.isdir(fpath):
                        if os.path.ismount(fpath):
                            os.system('umount -l %s' % fpath)
                        else:
                            shutil.rmtree(fpath)
                else:
                    cmd = "cat /etc/mtab | grep %s" % fpath
                    ret = utils.run(cmd, host=self.host)
                    if ret.stdout:
                        cmd = 'umount -l %s' % fpath
                        utils.run(cmd, host=self.host)
                    else:
                        cmd = 'rm -rf %s' % fpath
                        utils.run(cmd, host=self.host)
        deleted_files = set(bak) - set(cur) - set(self.permit_keys)
        if deleted_files:
            for fname in deleted_files:
                fpath = os.path.join(name['dir-name'], fname)
                LOGGER.warning('Restoring empty file %s', fpath)
                if not self.host:
                    open(fpath, 'a').close()
                else:
                    cmd = "touch %s" % fpath
                    utils.run(cmd, host=self.host)
        # TODO: record file/dir info and recover them separately

    def get_info(self, name):
        infos = {}
        infos['dir-name'] = name
        if self.host:
            ret = utils.run('ls -a %s' % name, host=self.host)
            for f in ret.stdout_lines:
                infos[f] = f
        else:
            for f in os.listdir(name):
                infos[f] = f
        return infos

    def get_names(self):
        return ['/var/lib/libvirt/images']


class FileState(State):
    name = 'file'
    permit_keys = []
    permit_re = []
    depend_states = ['ServiceState']

    def remove(self, name):
        raise Exception('It is not wise to remove a system file %s' % name)

    def restore(self, name):
        name = self.backup_state[name]
        file_path = name['file-path']
        cur = self.current_state[file_path]
        bak = self.backup_state[file_path]
        if cur['content'] != bak['content']:
            if self.host:
                utils.run_playbook('copy_file',
                                   hosts=self.host,
                                   private_key='libvirt-jenkins',
                                   ignore_fail=True,
                                   remote=self.host,
                                   file_content=bak['content'],
                                   file_path=file_path)
            else:
                with open(file_path, 'w') as f:
                    f.write(bak['content'])

    def get_info(self, name):
        infos = {}
        infos['file-path'] = name
        file_name = name
        if self.host:
            dir_path = '/tmp/%s_fetch/' % self.host
            file_name = dir_path + os.path.basename(name)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            utils.run_playbook('fetch_file',
                               hosts=self.host,
                               private_key='libvirt-jenkins',
                               ignore_fail=True,
                               remote=self.host,
                               file_path=name,
                               dir_path=dir_path)
        with open(file_name) as f:
            infos['content'] = f.read()
        if file_name != name:
            os.remove(file_name)
        return infos

    def get_names(self):
        return ['/etc/exports',
                '/etc/libvirt/libvirtd.conf',
                '/etc/libvirt/qemu.conf',
                '/etc/iscsi/initiatorname.iscsi']


class LVMState(State):
    name = 'LVM'
    permit_keys = []
    lvm = {}
    depend_states = ['ServiceState']

    def remove(self, name):
        ret = utils.run("vgremove -f %s" % name['name'], host=self.host)
        if ret.exit_code:
            raise Exception("Failed to delete %s: %s" % (name['name'],
                                                         ret.stderr))
        for pv in name['pvs']:
            utils.run("pvremove -y %s" % pv, host=self.host)

    def restore(self, name):
        try:
            self.lvm[name]
        except KeyError:
            LOGGER.debug("Skip restore VG: %s", name)
            return
        cur = self.current_state[name]
        bak = self.backup_state[name]
        new_lvs = set(cur['lvs'] - bak['lvs'])
        new_pvs = set(cur['pvs'] - bak['pvs'])
        for lv in new_lvs:
            utils.run("lvremove -f %s/%s" % (name, lv), host=self.host)
        for pv in new_pvs:
            utils.run("pvremove -y %s" % pv, host=self.host)

    def get_info(self, name):
        return self.lvm[name]

    def get_names(self):
        keys = ['name', 'pvs', 'lvs']
        cmd = 'vgs --noheadings -o '
        names = utils.run(cmd + 'vg_name',
                          host=self.host).stdout.strip().splitlines()
        for vg in names:
            lvs = utils.run(cmd + 'lv_name ' + vg,
                            host=self.host).stdout.strip().splitlines()
            pvs = utils.run(cmd + 'pv_name ' + vg,
                            host=self.host).stdout.strip().splitlines()
            record = dict(zip(keys, [vg, pvs, lvs]))
            self.lvm[vg] = record
        return names


class ISCSIState(State):
    name = 'iscsi'
    permit_keys = ['id']
    session = {}
    depend_states = ['ServiceState', 'LVMState', 'PoolState']

    def remove(self, name):
        session = name
        ret = utils.run("iscsiadm -m node -u -T %s" % session['target'],
                        host=self.host)
        if ret.exit_code:
            raise Exception("Failed to logout %s: %s" % (session['target'],
                                                         ret.stderr))

    def restore(self, name):
        name = session = self.backup_state[name]
        cmd = ("iscsiadm --mode node --login --targetname %s --portal %s"
               % (session['target'], session['portal']))
        ret = utils.run(cmd, host=self.host)
        if ret.exit_code:
            raise Exception("Failed to login %s: %s" % (session['target'],
                                                        ret.stderr))

    def get_info(self, name):
        return self.session[name]

    def get_names(self):
        names = []
        try:
            cmd_result = utils.run('iscsiadm -m session', host=self.host)
            lines = cmd_result.stdout.strip().splitlines()
        except (utils.AnsibleRunError, utils.CmdError):
            if 'No active sessions' not in cmd_result.stderr:
                raise
            return names
        for line in lines:
            match_obj = re.search(r'(\w+): \[(\d+)\] (\S+),\d+ (\S+)', line)
            if match_obj is None:
                continue
            values = match_obj.groups()
            keys = ['protocol', 'id', 'portal', 'target']
            record = dict(zip(keys, values))
            session_target = record['target']
            names.append(session_target)
            self.session[session_target] = record
        return names


class LIOISCSIState(State):
    name = 'lio iscsi'
    permit_keys = []
    nodes = {}
    node_path = '/iscsi'
    depend_states = ['ServiceState', 'LVMState', 'ISCSIState']

    def remove(self, name):
        cmd = "targetcli %s delete %s" % (self.node_path, name['name'])
        ret = utils.run(cmd, host=self.host)
        if ret.exit_code:
            raise Exception("Failed to delete %s: %s" % (name['name'],
                                                         ret.stderr))

    def restore(self, name):
        # Only remove new luns
        name = self.backup_state[name]
        target_name = name['name']
        try:
            self.current_state[target_name]
        except KeyError:
            LOGGER.debug("Skip restore LIO iscsi target: %s", target_name)
            return
        cur = self.current_state[target_name]
        bak = self.backup_state[target_name]
        new_luns = set(cur['luns']) - set(bak['luns'])
        cmd = 'targetcli /iscsi/%s/tpg1/luns delete ' % target_name
        for lun in new_luns:
            ret = utils.run(cmd + lun, host=self.host)
            if ret.exit_code:
                raise Exception("Failed to delete lun %s: %s" % (lun,
                                                                 ret.stderr))

    def get_info(self, name):
        return self.nodes[name]

    def get_names(self):
        names = []
        keys = ['name', 'luns']
        try:
            cmd = "targetcli ls %s 1" % self.node_path
            output = utils.run(cmd, host=self.host).stdout.strip()
            start_index = 1
            if 'Warning: Could not load preferences file' in output:
                start_index = 2
            target_lines = output.splitlines()[start_index:]
            for target in target_lines:
                name = target.split()[1]
                cmd = "targetcli ls /iscsi/%s/tpg1/luns 1" % name
                luns_lines = utils.run(cmd,
                                       host=self.host).stdout.strip()

                luns = [lun.split()[1] for lun in luns_lines.splitlines()[1:]]
                record = dict(zip(keys, [name, luns]))
                names.append(name)
                self.nodes[name] = record
        # pylint: disable=broad-except
        except Exception as e:
            LOGGER.error("Fail to get lio status: %s", e)
            # Reset names to empty
            names = []
        return names


class LIOFileioState(State):
    name = 'lio backstores fileio'
    permit_keys = []
    nodes = {}
    node_path = '/backstores/fileio'
    depend_states = ['ServiceState', 'LVMState', 'ISCSIState', 'LIOISCSIState']

    def remove(self, name):
        cmd = "targetcli %s delete %s" % (self.node_path, name['name'])
        ret = utils.run(cmd, host=self.host)
        if ret.exit_code:
            raise Exception("Failed to delete %s: %s" % (name['name'],
                                                         ret.stderr))
        if os.path.isfile(name['backing_file']):
            os.remove(name['backing_file'])

    def restore(self, name):
        LOGGER.debug("Skip restore LIO fileio objects: %s", name['name'])

    def get_info(self, name):
        return self.nodes[name]

    def get_names(self):
        names = []
        keys = ['name', 'backing_file']
        try:
            cmd = "targetcli ls %s 1" % self.node_path
            output = utils.run(cmd, host=self.host).stdout.strip()
            start_index = 1
            if 'Warning: Could not load preferences file' in output:
                start_index = 2
            fileio_lines = output.splitlines()[start_index:]
            for line in fileio_lines:
                name = line.split()[1]
                backing_file = line.split()[3][1:]
                record = dict(zip(keys, [name, backing_file]))
                names.append(name)
                self.nodes[name] = record
        # pylint: disable=broad-except
        except Exception as e:
            LOGGER.error("Fail to get lio status: %s", e)
            # Reset names to empty
            names = []
        return names


class TgtState(State):
    name = 'tgt'
    permit_keys = []
    nodes = {}
    depend_states = ['ServiceState', 'LVMState', 'ISCSIState']

    def remove(self, name):
        target = name
        cmd = "tgtadm --lld iscsi --mode target --op delete --tid %s"
        ret = utils.run(cmd % target['tid'], host=self.host)
        if ret.exit_code:
            raise Exception("Failed to delete %s: %s" % (target['name'],
                                                         ret.stderr))
        for backing_file in target['lun_info'].values():
            if os.path.isfile(backing_file):
                os.remove(backing_file)

    def restore(self, name):
        # Only remove new luns
        name = self.backup_state[name]
        target_name = name['name']
        try:
            self.current_state[target_name]
        except KeyError:
            LOGGER.debug("Skip restore tgt iscsi target: %s", target_name)
            return
        cur = self.current_state[target_name]
        bak = self.backup_state[target_name]
        new_luns, _, _ = utils.diff_dict(bak['lun_info'], cur['lun_info'])
        cmd = "tgtadm --lld iscsi --mode logicalunit --op delete"
        cmd += " --tid %s --lun " % name['tid']
        for lun in new_luns:
            ret = utils.run(cmd + lun, host=self.host)
            if ret.exit_code:
                raise Exception("Failed to delete lun %s: %s" % (lun,
                                                                 ret.stderr))
            if os.path.isfile(cur['lun_info'][lun]):
                os.remove(cur['lun_info'][lun])

    def get_info(self, name):
        return self.nodes[name]

    def get_names(self):
        names = []
        cmd = 'tgtadm --lld iscsi --mode target --op show'
        targets = utils.run(cmd,
                            host=self.host).stdout.strip().split('Target ')
        target_pat = r'(\d+): (\S+)'
        lun_pat = r'(\d+).*Backing store path: (\S+)'
        keys = ['tid', 'name', 'lun_info']
        for target in [t for t in targets if t]:
            try:
                tid, name = re.search(target_pat, target).groups()
                lun_info = {}
                for lun in target.strip().split('LUN: ')[1:]:
                    lun_id, lun_file = re.search(lun_pat, lun,
                                                 re.DOTALL).groups()
                    lun_info[lun_id] = lun_file
                record = dict(zip(keys, [tid, name, lun_info]))
                names.append(name)
                self.nodes[name] = record
            # pylint: disable=broad-except
            except Exception as e:
                LOGGER.error("Fail to get tgt status: %s", e)
                # Reset names to empty
                names = []
        return names
