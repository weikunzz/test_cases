How To Get Started?
*******************


Install libvirt-ci as package
=============================

libvirt-ci could be installed as package on your host from the repo.
Recommend install the package in virtualenv, make sure pip and
virtualenv installed on your host.

1. Clone libvirt-ci repo
::

    $ git clone http://git.host.prod.eng.bos.redhat.com/git/libvirt-ci

2. Install libvirt-ci
::

    $ mkdir ~/libvirt-ci-testenv
    $ pip install --use-wheel --upgrade pip virtualenv
    $ virtualenv -p `which python2` ~/libvirt-ci-testenv
    $ source ~/libvirt-ci-testenv/bin/activate

    Change dir to libvirt-ci

    (libvirt-ci-testenv) [user@localhost libvirt-ci]$ make install

.. note:: If not fresh install, run

    $ make clean-install

.. note:: Make sure "java pyparsing python-devel postgresql-devel
          gcc libffi-devel openssl-devel libselinux-python"
          installed on your host.

4. Run ci command to check
::

    $ ci --help

Now ci command is ready to be used on your host, while the :term:`JJB` yaml
in the libvirt-ci repo could be used to generate jenkins jobs and update
to specific :term:`Jenkins Master`.

Please check :ref:`CI Command Reference` for command line reference.

Run libvirt CI locally
======================

Libvirt CI also support user to run ci command locally with same Jenkins
configuration, both pipeline and jobs params.

As show in diagram Libvirt CI Overview 0.0.2 from :ref:`Integration View`,
inside the pipleline jobs what's been executed are ci commands, which in
sequence as::

  ci provision --> ci run --> ci report* --> ci teardown

So at your local host with libvirt-ci installed, you could start at your
desired step with your CI pipeline.


If you haven't got a machine for your testing, run::

  $ ci provision

it will return you with a beaker machine with latest RHEL x86_64 OS tree
by default.

If you already have a machine with ssh access, while want to have env
setup (repo, package, etc.) same with our CI, you could specify your
target with provision options.

e.g. for a Power8 machine 'host-abc' located at US with RHEL7.5 OS
already installed and ssh passwordless connnetion ready, run::

  $ ci provision --target host-abc --product RHEL --version 7.5 --arch ppc64le --packages qemu-kvm-rhev,libvirt,wget

After you have login to the beaker machine and install libvirt-ci, you
could run::

  # ci run --only virsh.list

to run a small group of tp-libvirt test cases.

Or::

  # ci run --rerun https://libvirt-jenkins.rhev-ci-vms.eng.rdu2.redhat.com/view/libvirt/view/RHEL-7.5%20x86_64/job/libvirt-RHEL-7.5-runtest-x86_64-acceptance-general/

for run exact tests and config from jenkins job. The test result will be
saved in junit file in current dir.

Then to report your test result, run::

  $ ci report-to-metadash --junit your_junit_file.xml

The result will be stored on Metadash and routed to other connected service
or DB.

.. note:: The ci provision and run command are powerful, for command detail
          please check the :ref:`CI Command Reference`


Contribute to libvirt-ci
========================

Currently libvirt-ci is following Gerrit review workflow, submit Changes on
gerrit is welcomed.

Gerrit configuration
--------------------

Setup SSH key in gerrit

  1. Check your ssh key on gerrit::

      $ cat ~/.ssh/id_rsa.pub

    and check if your current is in existing keys in gerrit

  2. If you don’t have this file, you need to create it by running::

      $ ssh-keygen

  3. Navigate to https://code.engineering.redhat.com/gerrit/#/settings/ssh-keys

    If your key shown in last step is not in gerrit:

    Click “Add key” and paste it there, then “Add”.

  4. Test your key::

      $ ssh -p 29418 your_kerberos_id@code.engineering.redhat.com

    You’ll see welcome message.

Make change to the code
-----------------------

Git clone the code::

  $ git clone ssh://your_kerberos_id@code.engineering.redhat.com/libvirt-ci

Update git config with user name and email address::

  $ cd libvirt-ci

  Add user config with:

  $ vim .git/config
  [user]

  name = Your Name

  email = your_kerberos_id@redhat.com

Change to a working branch before you start::

  $ git branch                    # Make sure your are on master branch

  $ git pull                      # Always pull latest updates before start

  $ git checkout -b some_topic    # Create and move to a working branch

Change the code with your favorite editor/IDE

Check your code before commit::

  $ make check

  If check failed, fix it.

Commit after your fix is done::

  $ git diff

  Create a commit containing all your changes:

  $ git commit -a -s

  Follow `commit message seven rules` and save.

Submit your Change
------------------

Install git-review::

  $ dnf install git-review

  or

  $ pip install git-review

Submit Change for review::

  The .gitreview file already in the repo, simply run:

  $ git review

The Change ID link will be returned and gate jobs will be triggered, now in
review process.

If ci gate job return failure, check in job console, make your fix in your
topic branch::

  Do fix the code and commit:

  $ git commit -a

  Rebase and squash the commit into the original commit:

  $ git rebase -i master

    1. change the new commit from 'pick' to 's'
    2. update the commit message with keeping the original Change-ID

  Now send Change review again:

  $ git review

  As the Change-ID remained, gerrit will treat the change as latest Patch Sets
  and keep the Change review history.

The change need get +2 review before merge by maintainer, gate job will grant
+1 if check pass, then another reviewer need grant +1 before merge. Follow the
same rebase and update Change method to update your Changes according to
review.
