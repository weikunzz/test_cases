#!/usr/bin/python
# coding:utf-8
# -*- copyright -*-

import getopt
import icfs_util
import sys


# get local group list, contains tuple: ("group_name", "group_id")
def get_local_groups():
    group_list = []
    try:
        with open("/etc/group", "r") as fp:
            lines = fp.readlines()
    except IOError:
        return group_list

    for line in lines:
        var_list = line.split(":")
        if len(var_list) != 4:
            continue

        group_name = var_list[0]
        group_id = var_list[2]
        group_list.append((group_name, group_id))

    return group_list


# get local user list, contains tuple: ("user_name", "user_id", "group_id")
def get_local_users():
    user_list = []
    try:
        with open("/etc/passwd", "r") as fp:
            lines = fp.readlines()
    except IOError:
        return user_list

    for line in lines:
        var_list = line.split(":")
        if len(var_list) != 7:
            continue

        user_name = var_list[0]
        user_id = var_list[2]
        group_id = var_list[3]
        user_list.append((user_name, user_id, group_id))

    return user_list


def query():
    opts = []
    argv = []
    try:
        opts, argv = getopt.getopt(sys.argv[1:], 'ug', ['local', 'query'])
    except getopt.GetoptError:
        icfs_util.error('002')

    if len(opts) != 3 or argv != []:
        icfs_util.error('002')
    for k, v in opts:
        if k == "-u":
            query_user()
        elif k == "-g":
            query_group()


# print all local normal users
def query_user():
    group_list = get_local_groups()
    user_list = get_local_users()
    print '%-32s \t %-32s' % ('Username', 'Groupname')
    for user_name, user_id, group_id in user_list:
        if int(user_id) < icfs_util.get_min_uid():
            continue

        group_name = group_id
        for gname, gid in group_list:
            if gid == group_id:
                group_name = gname

        print '%-32s \t %-32s' % (user_name, group_name)


# print all local normal groups
def query_group():
    group_list = get_local_groups()
    print 'Groupname'
    for group_name, group_id in group_list:
        if int(group_id) < icfs_util.get_min_uid():
            continue

        print group_name
