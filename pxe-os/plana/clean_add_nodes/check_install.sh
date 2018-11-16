#!/bin/bash
rm -rf /root/.ssh/known_hosts
ips=($(awk '{print $1}' ./plana/ip.txt))
for i in ${ips[@]}
do
  command=${command}"ssh $i hostname && "
done
#command="ping -c "
command=${command% &&*}

echo "$command"

while true
do
  if eval $command
  then
    echo “install ok”
    break
  else
    echo "install error"
    sleep 30
  fi
done
