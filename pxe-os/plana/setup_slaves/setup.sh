#!/bin/bash
set -x

chkconfig --del init-icfs-client-backend-monitor
rm -rf /etc/rc.d/init.d/init-icfs-client-backend-monitor
echo 'service ntpd start' >> /etc/rc.d/rc.local
useradd ubuntu -m -G root -g root -s /bin/bash && echo ubuntu:000000 | chpasswd
cp -p /etc/ganesha/ganesha.conf /etc/ganesha/ganesha.conf.bak
cp -p /etc/httpd/conf/httpd.conf /etc/httpd/conf/httpd.conf.bak
mkdir /var/log/tclog
cp -p /setup_slaves/ntp.conf /etc
cp -p /setup_slaves/step-tickers /etc/ntp/
cp -p /setup_slaves/sudoers /etc
version=`icfs -v | awk '{print $3}'`
sed -i "s/version/v$version/g" /setup_slaves/CentOS-Base.repo
cp -p /setup_slaves/CentOS-Base.repo /etc/yum.repos.d
cp -p /setup_slaves/hosts /etc
cp -rp /setup_slaves/rootssh/.ssh /root/
cp -p /setup_slaves/ubuntussh/ubuntu-ssh.tar.gz /home/ubuntu
cp -p /setup_slaves/killfuse.sh /usr/bin
cd /home/ubuntu && tar -zxvf ubuntu-ssh.tar.gz
service ntpd restart

ip=`ifconfig eno16777984 | grep -w 'inet' | awk '{print $2}'`
name=`grep "$ip" /setup_slaves/hosts | awk '{print $2}' | grep -v "\."`
echo $name > /etc/hostname
yum install icfs-test -y
sed -i "s/dhcp/static/g" /etc/sysconfig/network-scripts/ifcfg-eno16777984
sed -i "PEERDNS=yes/d" /etc/sysconfig/network-scripts/ifcfg-eno16777984
sed -i "PEERROUTES=yes" /etc/sysconfig/network-scripts/ifcfg-eno16777984
echo "IPV6_PRIVACY=no" >> /etc/sysconfig/network-scripts/ifcfg-eno16777984
echo "IPADDR=$ip" >> /etc/sysconfig/network-scripts/ifcfg-eno16777984
echo "PREFIX=20" >> /etc/sysconfig/network-scripts/ifcfg-eno16777984
echo "GATEWAY=100.7.47.254" >> /etc/sysconfig/network-scripts/ifcfg-eno16777984
echo "NETMASK=255.255.240.0" >> /etc/sysconfig/network-scripts/ifcfg-eno16777984
service NetworkManager restart
service network restart
#systemctl restart network.service


echo "Done!!!"
