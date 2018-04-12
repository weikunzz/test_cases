References
**********
#. `Jenkins Job Builder <http://ci.openstack.org/jenkins-job-builder/>`_.
#. `Ansible Documentation <http://docs.ansible.com//>`_.
#. `Avocado <https://github.com/avocado-framework/avocado/>`_.
#. `Avocado-vt <https://github.com/avocado-framework/avocado-vt/>`_.
#. `tp-libvirt <https://github.com/autotest/tp-libvirt/>`_.
#. `caselink <https://github.com/Hao-Liu/caselink/>`_.
#. `libvirt-dashboard <https://github.com/ryncsn/libvirt-dashboard/>`_.
#. `Commit message seven rules <http://chris.beams.io/posts/git-commit/>`_.

Glossary
========

.. glossary::

   Ansible
       Section to indicate the execution of ansible playbooks

   Avocado
       Avocado is a test framework that is built on the experience accumulated with autotest, while improving on its weaknesses and shortcomings.

   Avocado-vt
       Avocado-VT is a compatibility plugin that lets you execute virtualization related tests (then known as virt-test), with all conveniences provided by Avocado.

   Beaker Specific
       **Note** this is not limited to these and the provisioner can use any keyword in a recipeset that is used in Beaker

       - recipesets - List of the below to specify different combinations of distro, family, variant, etc.
       - distro - Specify a distro name ex. RHEL-6.5
       - family - Specify a family of distributions ex. Red Hat Enterprise Linux 6
       - tag - Specify a tag with family ex. RTT
       - variant - Specify a variant ex. Server
       - arches - Specify system architectures ex. "arches": ["X86_64"]
       - hostrequire - Specify host requirements ex. "hostrequire": ["arch=X86_64"]
       - keyvalue - Specify key/value defined on a host ex. "keyvalue": ["MEMORY>1000", "DISKSPACE>20000"]
       - taskparam - Specify a parameter to the install or reserve task
       - bkr_data - Used to pass specific identifier to determine which machine is which

   ci-ops-central
       A repo that contains all the core of the code that handles provisioning and tearing down resources

   JJB
       (Jenkins Job Builder) - These are YAML files that populate a Jenkins Master with jobs


   JJB Macro
       Many of the actions of a Job, such as builders or publishers, can be defined as a Macro, and then that Macro used in the Job description.
       Check in JJB doc: `Macro <https://docs.openstack.org/infra/jenkins-job-builder/definition.html#macro/>`_


   Job Template
       If you need several jobs defined that are nearly identical, except
       perhaps in their names, SCP targets, etc., then you may use a Job
       Template to specify the particulars of the job, and then use a Project
       to realize the job with appropriate variable substitution. Any variables
       not specified at the project level will be inherited from the Defaults.
       Check in JJB doc: `job-template <https://docs.openstack.org/infra/jenkins-job-builder/definition.html#job-template/>`_

   Jenkins Master
       The core of where all jobs are run from and contains certain plugins to help drive provisioning and testing

   Jenkins Slave
       A system that is registered with the Jenkins Master to be used as a resource to run jobs on instead of using the Jenkins Master resources

   OpenStack
       Specific

       - flavor - This is an OpenStack concept and means the size of VM. These flavors define Memory, VCPUs, and Disk Size. Usually m1.tiny, m1.small, m1.medium, m1.large, m1.xlarge
       - image - This is an OpenStack term used to reference an image name

   packages

       - yum - String of yum packages
       - pip - String of pip packages

   Repositories
       Add yum repositories to jenkins slaves and test resources

       - name - name of repository
       - baseurl - If used then can't use mirrorlist
       - mirrorlist - If used then baseurl can't be used
       - skip_if_unavailable - Set to 0 by default
       - gpgcheck - Set to 0 by default
       - enabled -  Set to 1 by default

       Also a git repository.

   Test Tier
       Tier means tiered approach to testing.
       Tiers can be identified as containers for groups of tests (from multiple test type and levels) to be executed based on the time to execute, complexity, and importance.

   Tier0

       * Definition :
         Automated unit tests
         Minimal time needed to execute (minutes to 1 hour)
       * Process criteria :
         100% automated, must pass 100%
         Development maintains tests and reviews results

   Tier1

       * Definition :
         Component level functional tests
         Minimal time needed to execute (minutes to hours)
       * Process criteria :
         Executed after tier 0 passing
         100% automated and must pass 100%
         QE / Development maintains tests and reviews results

   Tier2

       * Definition :
         Integration level functional tests
         May include basic non-functional tests (security, performance regression, install, compose validation)
         Runs during nightly time frame
       * Process criteria :
         Executed after components pass tier 1 testing
         100% automated and must pass 100%
         QE  maintains tests and reviews results

   Tier3

       * Definition :
         System, scenario and  non-functional tests
         Test that don't fit in tier 2 due to time, complexity, and other  factors
       * Process criteria :
         Executed after components pass tier 1 testing
         100% automated
         QE maintains tests and reviews results

   Topology
       A file that describes a set of resources that will get provisioned.
       In the case of OpenStack this would be flavor and image and in Beaker this would be distro and arch


   tp-libvirt
       Libvirt test provider for Avocado-vt and virt-test, upstream project on github.

