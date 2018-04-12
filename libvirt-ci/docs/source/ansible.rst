Ansible Playbooks
*****************

Libvirt CI use :term:`Ansible` with setting resource or service remotely quite
often, so need to maintain the playbooks in the repo.

All playbooks are in dir::

  libvirt_ci/data/playbooks/

Libvirt CI run the playbooks in two ways:

  1. Run ansbile command in jenkins shell builder

    e.g. In libvirt static provisioner job::

      ansible-playbook -i ansible_inventory.txt \
      libvirt-ci/playbooks/static_provisioner.yaml \
      --tags provisioner \

  2. Use ansible API within ci command

    Most playbooks are consumed this way, with the function::

      libvirt_ci.utils.run_playbook

    e.g. With 'ci build-guest-image' command::

      $ vim libvirt_ci/commands/build_guest_image.py +80

    .. code-block:: python
       :emphasize-lines: 1

       utils.run_playbook('guest_image_builder', private_key='libvirt-jenkins',
                          debug=True, distro=distro, product=product,
                          version=version, arch=arch, url_prefix=url_prefix,
                          timeout=180000)

