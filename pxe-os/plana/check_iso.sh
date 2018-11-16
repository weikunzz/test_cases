#!/bin/bash
set -x
iso_path=$1
iso_name=$2
http_path=$3
mount_path=$4
icfs_version=${iso_name%-linux*}
#判断iso是否发布
if [ ! -d $http_path/$icfs_version ]; then
  echo "----> New dir: $http_path/$icfs_version" 
  mkdir $http_path/$icfs_version
else
  echo "----> $http_path/$icfs_version already exists"
  rm -rf $http_path/$icfs_version
  mkdir $http_path/$icfs_version
fi
#判断是否存在iso挂载目录
if [ ! -d $mount_path ]; then
  echo "----> New dir: $mount_path" 
  mkdir -p $mount_path
else
  echo "----> $mount_path already exists!"
fi
#判断iso是否挂载
LINE=`mount | grep $mount_path | awk 'END{print NR}'`
if [ $LINE -ge 1 ]; then
  echo "----> iso is mounted, umount it"
  umount -l $mount_path
fi
sleep 5
echo "----> delete $mount_path/* "
rm -rf $mount_path/*
echo "----> 挂载iso"
mount -o loop $iso_path/$iso_name $mount_path
echo "----> 拷贝iso内容到http发布目录"
cp -rf $mount_path/* $http_path/$icfs_version/
echo "----> 拷贝setup_slaves.tar.gz包到发布目录"
cp -p ./plana/setup_slaves.tar.gz $http_path/$icfs_version/

echo "OK"
