#!/usr/bin/python
#coding:utf-8
import sys
import icfs_admin_user_local_delete 
import icfs_admin_user_local_create 
import icfs_admin_user_local_query
import icfs_admin_user_local_set
import icfs_util
    

def local():
    if '--query' in sys.argv:
        icfs_admin_user_local_query.query()
        
    elif '--create' in sys.argv: 
        icfs_admin_user_local_create.user_create()
        
    elif '--delete' in sys.argv:
        icfs_admin_user_local_delete.delete()
        
    elif '--set' in sys.argv:
        icfs_admin_user_local_set.set()
    else:
        icfs_util.error('002')
