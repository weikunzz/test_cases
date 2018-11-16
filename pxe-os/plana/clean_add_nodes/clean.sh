#!/bin/bash
set -x
ssh -t -p 22 root@100.7.40.14 << EOF
su - postgres
psql
\\c paddles

delete from job_nodes USING jobs where job_nodes.job_id=jobs.id and jobs.machine_type='plana';
delete from jobs where machine_type='plana';
delete from runs where machine_type='plana';
delete from nodes where machine_type='plana';
\\q

exit
EOF
