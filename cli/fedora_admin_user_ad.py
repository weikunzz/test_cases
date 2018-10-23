#!/usr/bin/python
#coding:utf-8
# -*- copyright -*-
import sys
import icfs_util
import icfs_admin_user_ad_join
import icfs_admin_user_ad_test
import icfs_admin_user_ad_query
import icfs_admin_user_ad_quit

def ad():

    if '--join' in  sys.argv:
        icfs_admin_user_ad_join.join()
    elif '--query' in  sys.argv:
        icfs_admin_user_ad_query.query()
    elif '--test' in  sys.argv:
        icfs_admin_user_ad_test.test()
    elif '--quit' in  sys.argv:
        icfs_admin_user_ad_quit.quit()
    else :
        icfs_util.error('002')