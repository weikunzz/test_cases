#!/bin/bash

#######################
# Run a specific test #
#######################

set -xe

# This is a workaround for following bug. When running job under Jenkins
# the TERM env may not exists.
# https://bugzilla.redhat.com/show_bug.cgi?id=1432303
# This workaround should be removed either:
# 1) When the bug is resolved
# 2) When Jenkins is deprecated
# 3) When a new workaround database is established.
if [ -z "$TERM" ] || [ "$TERM" = "dumb" ]; then
    export TERM=xterm-256color
fi

# Prepare SELinux for testing (Should be moved to virt-test-ci)
setsebool virt_use_nfs 1
chcon -R system_u:object_r:virt_image_t:s0 $WORKSPACE 2>&1 >&/dev/null
setenforce 1

yum install ntpdate ntp -y
service ntpd stop
ntpdate -v clock.util.phx2.redhat.com || true

# Prepare required packages. All repo/package preparation will be
# moved to one place in the future.
yum install tcpdump policycoreutils-python -y
pip install aexpect junit-xml unittest2 --upgrade
if [ $CI_TEST_FRAMEWORK = "libvirt-tck" ]
then
    set +e
    if grep -q -i "release 7" /etc/redhat-release
    then
        yum install iscsi-initiator-utils targetcli\* -y --skip-broken
        iscsiadm --mode node -u
        iscsiadm --mode node -o delete
        sync
        service iscsid stop
        sync
        targetcli backstores/fileio/ delete device.ci-tck-iscsi && sync && rm -f /var/tmp/ci-tck-iscsi
        sync
        targetcli /iscsi delete iqn.2016-08.com.virttest:ci-tck-iscsi.target && sync
        targetcli backstores/fileio/ create name=device.ci-tck-iscsi file_or_dev=/var/tmp/ci-tck-iscsi size=5G
        sync
        targetcli iscsi/ create iqn.2016-08.com.virttest:ci-tck-iscsi.target
        targetcli iscsi/iqn.2016-08.com.virttest:ci-tck-iscsi.target/tpg1/luns create /backstores/fileio/device.ci-tck-iscsi
        targetcli /iscsi/iqn.2016-08.com.virttest:ci-tck-iscsi.target/tpg1/ set attribute authentication=0 demo_mode_write_protect=0 generate_node_acls=1 cache_dynamic_acls=1
        targetcli / saveconfig
        sync
        echo "InitiatorName=iqn.2016-08.com.virttest:ci-tck-iscsi.target" > /etc/iscsi/initiatorname.iscsi
        sync
        service iscsid start
        iscsiadm --mode discoverydb --type sendtargets --portal 127.0.0.1 --discover
        iscsiadm --mode node --targetname iqn.2016-08.com.virttest:ci-tck-iscsi.target --portal 127.0.0.1:3260 --login
    fi
    set -e
fi
if [ $CI_TEST_FRAMEWORK = "test-api" ] || [ $CI_TEST_FRAMEWORK = "install" ]
then
    set +e
    yum install lsof dosfstools patch genisoimage pexpect nmap libvirt\* qemu-kvm-rhev libvirt-python\* syslinux tftp tftp-server cyrus-sasl-gssapi glusterfs-server -y --skip-broken

    service glusterd start
    cp /usr/share/syslinux/pxelinux.0 /var/lib/tftpboot
    mkdir -p /var/lib/tftpboot/pxelinux.cfg
    sed -i 's/= -s \/var\/lib\/tftpboot/= -c -s \/var\/lib\/tftpboot/g' /etc/xinetd.d/tftp
    sed -i 's/disable[      ][      ][      ]= yes/disable = no/g' /etc/xinetd.d/tftp
    service xinetd restart

    iscsiadm --mode node -u
    iscsiadm --mode node -o delete

    sync

    service iscsid stop

    sync

    if grep -q -i "release 7" /etc/redhat-release
    then
        yum install targetcli\* ceph-common sshpass -y --skip-broken
        targetcli backstores/fileio/ delete libvirt_test_api_logical && sync && rm -f /var/tmp/libvirt_test_api_iscsi_logical.img
        sync

        targetcli backstores/fileio/ create name=libvirt_test_api_logical file_or_dev=/var/tmp/libvirt_test_api_iscsi_logical.img size=20G
        sync

        targetcli iscsi/ create iqn.2016-03.com.redhat.englab.nay:libvirt-test-api-logical

        targetcli iscsi/iqn.2016-03.com.redhat.englab.nay:libvirt-test-api-logical/tpg1/acls create iqn.2016-03.com.redhat.englab.nay:libvirt-test-api-client

        targetcli iscsi/iqn.2016-03.com.redhat.englab.nay:libvirt-test-api-logical/tpg1/luns create /backstores/fileio/libvirt_test_api_logical

        sshpass -p "redhat" scp root@10.73.75.154:/etc/ceph/ceph* /etc/ceph

        ceph osd lspools | grep "test-api-pool"
        if echo $?
        then
            ceph osd pool create test-api-pool 128 128
        fi

    else
        yum install perl-Config-General scsi-target-utils -y --skip-broken
        service tgtd stop
        sync

        mkdir -p /var/lib/tgtd/
        rm -f /var/lib/tgtd/libvirt_test_api_iscsi.img
        dd if=/dev/zero of=/var/lib/tgtd/libvirt_test_api_iscsi.img bs=2M seek=10000 count=0
        sync

        echo "
        default-driver iscsi
        <target iqn.2016-03.com.redhat.englab.nay:libvirt-test-api-logical>
        backing-store /var/lib/tgtd/libvirt_test_api_iscsi.img
        allow-in-use yes
        </target>

        " > /etc/tgt/targets.conf
        restorecon -R /var/lib/tgtd
        service tgtd start
    fi

    echo "InitiatorName=iqn.2016-03.com.redhat.englab.nay:libvirt-test-api-client" > /etc/iscsi/initiatorname.iscsi

    sync

    service iscsid start

    iscsiadm --mode discoverydb --type sendtargets --portal 127.0.0.1 --discover
    iscsiadm --mode node --targetname iqn.2016-03.com.redhat.englab.nay:libvirt-test-api-logical --portal 127.0.0.1:3260 --login

    # Replace default disk name
    disk_name="\/dev\/"$(iscsiadm -m session -P 3 |grep 'Attached scsi disk '|awk '{{print $4}}')
    export CI_REPLACES=$(sed -e "s/global\.cfg:/global\.cfg:\n\'\/dev\/sdb\'-->\'${{disk_name}}\'/" <<< "$CI_REPLACES")

    sync

    echo -e 'o\nn\np\n1\n\n\nw\n' | fdisk /dev/sdb

    modprobe -r scsi_debug

    modprobe scsi_debug dev_size_mb=1000
    set -e
fi

# Workaround for NSS BZ#1317691 for v2v testing
if [ $CI_VT_TYPE = "v2v" ]
then
    export NSS_STRICT_NOFORK=DISABLED
fi

# Tell runner some detail to record when reporting
# Thoese parameters can't be extrated from any other where, so expose
# them as env variables directly
export CI_PRODUCT="{product}"
export CI_PRODUCT_VERSION="{version}"
export CI_COMPONENT="{component}"
export CI_SHOW_PACKAGES="{show-packages}"
export CI_LABEL_PACKAGE="{label-package}"
export CI_TEST_NAME="{test-name}"
export CI_TEST_TYPE="{test-type}"
export CI_TEST_SUFFIX="{test-suffix}"
export CI_JOB_NAME="{name}"  # Same value with $JOB_NAME

# Run test
if [ $CI_QEMU_RHEV = "true" ]
then
    export CI_QEMU_PKG="rhev"
    export CI_REPORT="$WORKSPACE/result_rhev.xml"
    export CI_TEXT_REPORT="$WORKSPACE/report_rhev.txt"
    ci run --clean-env
fi

if [ $CI_QEMU_RHEL = "true" ]
then
    # Append additional entries to CI_NO
    if [[ ! -z $CI_RHEL_NO ]]
    then
        export CI_NO=$CI_NO$'\n'$CI_RHEL_NO
    fi
    export CI_QEMU_PKG="rhel"
    export CI_REPORT="$WORKSPACE/result_rhel.xml"
    export CI_TEXT_REPORT="$WORKSPACE/report_rhel.txt"
    ci run --clean-env
fi
