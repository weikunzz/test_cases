# -*- coding: utf-8 -*-

import os
import salt.utils
import salt.key
import salt.client


def list_hosts():
    opt = {
        'transport': 'zeromq',
        '__role': 'master',
        'sock_dir': '/var/run/salt/master',
        'pki_dir': '/etc/salt/pki/master'
    }
    key = salt.key.Key(opt)
    keys = key.list_keys()
    return keys['minions'] if 'minions' in keys else []


def run_ping(tgt):
    local = salt.client.get_local_client()

    kwargs = dict()
    kwargs['fun'] = 'test.ping'
    kwargs['arg'] = []
    kwargs['timeout'] = 5
    kwargs['show_timeout'] = True
    kwargs['show_jid'] = False
    kwargs['delimiter'] = ':'
    if ',' in tgt:
        tgt_list = tgt.split(',')
        tgt_list = [i for i in tgt_list if i != '']
        kwargs['tgt'] = tgt_list
        kwargs['expr_form'] = 'list'
    else:
        kwargs['tgt'] = tgt
        kwargs['expr_form'] = 'glob'

    ret_dict = {}
    for full_ret in local.cmd_cli(**kwargs):
        for node_name, node_ret in full_ret.items():
            status = True if node_ret['ret'] is True else False
            ret_dict[node_name] = {"status": status}
    return ret_dict


def run_cmd(tgt, cmd_line):
    local = salt.client.get_local_client()

    kwargs = dict()
    kwargs['fun'] = 'cmd.run_all'
    kwargs['arg'] = [cmd_line]
    kwargs['timeout'] = 5
    kwargs['show_timeout'] = True
    kwargs['show_jid'] = False
    kwargs['delimiter'] = ':'
    if ',' in tgt:
        tgt_list = tgt.split(',')
        tgt_list = [i for i in tgt_list if i != '']
        kwargs['tgt'] = tgt_list
        kwargs['expr_form'] = 'list'
    else:
        kwargs['tgt'] = tgt
        kwargs['expr_form'] = 'glob'

    ret_dict = {}
    for full_ret in local.cmd_cli(**kwargs):
        for node_name, node_ret in full_ret.items():
            ret_code = -1
            std_out = ""
            std_err = ""
            ret_value = node_ret["ret"]
            if not isinstance(ret_value, dict):
                ret_dict[node_name] = {"retcode": ret_code, "stdout": std_out, "stderr": std_err}
                continue

            if "retcode" in ret_value:
                ret_code = ret_value["retcode"]
            if "stdout" in ret_value:
                std_out = ret_value["stdout"]
            if "stderr" in ret_value:
                std_err = ret_value["stderr"]
            ret_dict[node_name] = {"retcode": ret_code, "stdout": std_out, "stderr": std_err}
    
    return ret_dict


def _file_dict(fn_):
    if not os.path.isfile(fn_):
        err = 'The referenced file, {0} is not available.'.format(fn_)
        raise ValueError(err)
    with salt.utils.fopen(fn_, 'r') as fp_:
        data = fp_.read()
    return {fn_: data}


def run_copy(tgt, src, dest):
    local = salt.client.get_local_client()

    arg = [_file_dict(src), dest]
    kwargs = dict()
    kwargs['fun'] = 'cp.recv'
    kwargs['arg'] = arg
    kwargs['timeout'] = 5
    kwargs['show_timeout'] = True
    kwargs['show_jid'] = False
    kwargs['delimiter'] = ':'
    if ',' in tgt:
        tgt_list = tgt.split(',')
        tgt_list = [i for i in tgt_list if i != '']
        kwargs['tgt'] = tgt_list
        kwargs['expr_form'] = 'list'
    else:
        kwargs['tgt'] = tgt
        kwargs['expr_form'] = 'glob'

    ret_dict = {}
    for full_ret in local.cmd_cli(**kwargs):
        for node_name, node_ret in full_ret.items():
            ret_code = 1
            ret_out = ""
            if 'ret' not in node_ret:
                ret_dict[node_name] = {"retcode": ret_code, "retout": ret_out}
                continue

            ret = node_ret['ret']
            if isinstance(ret, dict):
                if True in ret.values():
                    ret_code = 0
            elif isinstance(ret, str):
                if 'Minion did not return' in ret:
                    ret_code = -1
                    ret_out = ret

            ret_dict[node_name] = {"retcode": ret_code, "retout": ret_out}
    
    return ret_dict
