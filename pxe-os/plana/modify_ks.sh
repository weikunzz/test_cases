#!/bin/sh
#modify /var/www/html/icfs-3.6.5.4/ks.cfg
set -x
cp -p $1/$2/isolinux/ks.cfg $1/$2/
chmod 755 $1/$2/ks.cfg

sed -i "s/cdrom/url --url=http:\/\/100.7.40.160\/$2\//g" $1/$2/ks.cfg
sed -i "/bootloader --append/d" $1/$2/ks.cfg
sed -i "/clearpart --all --initlabel --drives=sda/d" $1/$2/ks.cfg
sed -i "/network  --hostname=inspur --bootproto=dhcp --onboot=on/a\network  --bootproto=dhcp --device=eno16777984 --ipv6=auto\nnetwork  --hostname=localhost.localdomain" $1/$2/ks.cfg
sed -i '/user --name=icfs/a\bootloader --append="rhgb quiet crashkernel=auto" --location=mbr --boot-drive=sda\nautopart --type=lvm\nclearpart --all --initlabel --drives=sda' $1/$2/ks.cfg
sed -i "/run\/install\/repo/d" $1/$2/ks.cfg
sed -i "/^mkdir \/mnt\/sysimage\/root\/src/a\wget -P \/mnt\/sysimage\/ http:\/\/100.7.40.160\/$2\/icfs.tar.gz\nwget -P \/mnt\/sysimage\/root\/src\/ http:\/\/100.7.40.160\/$2\/custom.tar.gz\nwget -P \/mnt\/sysimage\/ http:\/\/100.7.40.160\/$2\/setup_slaves.tar.gz" $1/$2/ks.cfg
sed -i "/cd \/ \&\& tar -xzf icfs.tar.gz/a\cd / \&\& tar -xzf setup_slaves.tar.gz" $1/$2/ks.cfg
sed -i "/\/icfs\/sh\/setup_server.sh/a\\/setup_slaves\/setup.sh" $1/$2/ks.cfg
