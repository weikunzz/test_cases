#!/bin/bash
set -x
rm -rf /root/.ssh/known_hosts 
#ips="161 162 163"
ips=($(awk '{print $1}' ./plana/ip.txt))
echo ${ips[@]}
for i in ${ips[@]}
do
   ssh -t -p 22 root@${i} "dd if=/dev/zero of=/dev/sda bs=446 count=1"
   ssh -t -p 22 root@${i} "hexdump -C -n 446  /dev/sda"
   ssh -t -p 22 root@${i} "hexdump -C -n 446 -v /dev/sda"
   ssh -t -p 22 root@${i} "reboot"
done

 
exit 0
