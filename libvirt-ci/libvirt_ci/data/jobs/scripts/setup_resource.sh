#!/bin/bash

#####################################################
# Setup resource node for migrate remote-access etc #
#####################################################

set -xe

touch /tmp/host_vars.txt
if [ "{provision_resource}" = "enable" ]
then
    # Prepare ansible inventory ini file
    printf "[local]\nlocalhost   ansible_connection=local\n\n[testsystems]\n" > $WORKSPACE/ansible_inventory.txt
    echo "$EXISTING_NODES" | tr , \\n >> $WORKSPACE/ansible_inventory.txt

    # chmod private key to 0600
    chmod 0600 $WORKSPACE/libvirt-ci/config/keys/libvirt-jenkins

    IMGURL={img-url}
    IMGPATH=/usr/share/avocado/data/avocado-vt/images
    IMGDEST=/usr/share/avocado/data/avocado-vt/images/jeos-19-64.qcow2
    INSTALLGUEST=no
    GUESTNAME=avocado-vt-vm1

    # Define extra parameters for ansible-playbook
    if [[ $JOB_NAME == *"remote_access"* ]]
    then
        INSTALLGUEST=yes
    elif [[ $JOB_NAME == "libvirt-python"*"migration"* ]]
    then
        IMGPATH=/var/lib/libvirt/images
        IMGDEST=/var/lib/libvirt/images/libvirt-test-api
    elif [[ $JOB_NAME == *"migration"* ]]
    then
        GUESTNAME=avocado-vt-remote-vm1
        INSTALLGUEST=yes
        IMGPATH=/var/lib/libvirt/images-remote-guest
        IMGDEST=/var/lib/libvirt/images-remote-guest/jeos-27-x86_64.qcow2
    fi
    extra_param="--extra-vars {{\"install_guest\":\"$INSTALLGUEST\",\"img_url\":\"$IMGURL\",\"img_path\":\"$IMGPATH\",\"img_dest\":\"$IMGDEST\",\"install_guest_name\":\"$GUESTNAME\"}}"

    # Run ansible playbook
    ansible-playbook -i $WORKSPACE/ansible_inventory.txt $WORKSPACE/libvirt-ci/playbooks/ansible_resource.yaml $extra_param --tags=beaker --private-key=$WORKSPACE/libvirt-ci/config/keys/libvirt-jenkins
    TR_STATUS=$?
    if [ "$TR_STATUS" != 0 ]; then echo -e "ERROR: Setup resource\nSTATUS: $TR_STATUS"; exit 1; fi
fi
