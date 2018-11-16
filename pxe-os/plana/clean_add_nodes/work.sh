#!/bin/bash
set -x

sleep 3600
ssh -t -p 22 root@100.7.40.14 << EOF

su - teuthology
source /home/teuthology/src/teuthology_master/virtualenv/bin/activate
cd /home/teuthology/src/icfs-qa-suite_master/suites/JupiterFull-Ansible
for i in `ls`;do teuthology-suite -v -s JupiterFull-Ansible/$i -c as-10.2.3-develop -f basic -t master -m plana -d centos --suite-branch master --suite-dir /home/teuthology/src/icfs-qa-suite_master;done 

EOF
