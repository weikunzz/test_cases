#!/usr/bin/python
# coding:utf-8

import sys
import icfs_admin_user_nis_join
import icfs_admin_user_nis_quit
import icfs_admin_user_nis_test
import icfs_admin_user_nis_query
import icfs_util

def nis():

    if '--query' in sys.argv:
        icfs_admin_user_nis_query.query()
    elif '--test' in sys.argv: 
        icfs_admin_user_nis_test.test()
    elif '--join' in sys.argv:
        icfs_admin_user_nis_join.join()
    elif '--quit' in sys.argv:
        icfs_admin_user_nis_quit.quit_nis()
    else:
        icfs_util.error('002')