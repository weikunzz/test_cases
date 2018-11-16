#!/bin/bash
set -x

nodes=($(awk '{print $2}' ./plana/ip.txt))

ssh -t -p 22 root@100.7.40.14 << EOF

su - teuthology
source /home/teuthology/src/teuthology_master/virtualenv/bin/activate
python /home/teuthology/src/teuthology_master/create_nodes_plana.py
teuthology-lock --unlock --owner inspur ${nodes[@]}
deactivate
exit
EOF
