#!/bin/bash
ips=($(awk '{print $1}' ./plana/ip.txt))
for i in ${ips[@]}
do
  ssh -t -p 22 root@${i} "sed -i '13s/^/#/' /var/spool/cron/root"
done
