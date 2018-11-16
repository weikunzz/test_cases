#!/bin/bash

set -x

function expect_ignore()
{
        if $@
        then
                return 0
        else
                return 0
        fi
}

expect_ignore sudo pgrep icfs-fuse |xargs sudo kill -9

expect_ignore sudo ps -ef | grep /mnt/icfs | grep -v "grep" | awk -F " " '{print $2}' | xargs sudo kill -9

expect_ignore sudo umount -l /mnt/icfs

expect_ignore sudo pgrep /home/nfs |xargs sudo kill -9

expect_ignore sudo ps -ef | grep /home/nfs | grep -v "grep" | awk -F " " '{print $2}' | xargs sudo kill -9

expect_ignore sudo umount -l /home/nfs

#expect_ignore sudo rm -rf /etc/salt/

expect_ignore sudo userdel testuser1
expect_ignore sudo userdel qin
expect_ignore sudo userdel inspur123
expect_ignore sudo userdel usert1
expect_ignore sudo groupdel testgroup1
expect_ignore sudo groupdel inspur
expect_ignore sudo groupdel qin
expect_ignore sudo groupdel inspur123
expect_ignore sudo groupdel cifstestgroup1
expect_ignore sudo userdel u800 2>/dev/null
expect_ignore sudo userdel u801 2>/dev/null
expect_ignore sudo userdel u802 2>/dev/null
expect_ignore sudo userdel u803 2>/dev/null
expect_ignore sudo groupdel g800 2>/dev/null
expect_ignore sudo groupdel g801 2>/dev/null
expect_ignore sudo groupdel g802 2>/dev/null
