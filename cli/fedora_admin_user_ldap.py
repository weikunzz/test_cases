#!/usr/bin/python
# coding:utf-8
# -*- copyright -*-

import sys
import icfs_util
import icfs_admin_user_ldap_join
import icfs_admin_user_ldap_test
import icfs_admin_user_ldap_query
import icfs_admin_user_ldap_quit

def ldap():

    if '--join' in  sys.argv:
        icfs_admin_user_ldap_join.join()
    elif '--quit' in sys.argv:
        icfs_admin_user_ldap_quit.quit_ldap()
    elif '--query' in  sys.argv:
        icfs_admin_user_ldap_query.query()
    elif '--test' in  sys.argv:
        icfs_admin_user_ldap_test.test()
    else :
        icfs_util.error('002')