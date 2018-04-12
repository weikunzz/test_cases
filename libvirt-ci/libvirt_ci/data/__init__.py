"""
All resource files are packaged and distributed as part of libvirt_ci package by pip

Libvirt-CI have to interact with test frameworks and work with many system utils,
so we need a workspace, to store rw datas, which is ~/.libvirt-ci
"""
# pylint: disable=import-error
import shutil
import os

# For ro libvirt-ci data
PATH = RESOURCE_PATH = os.path.dirname(os.path.abspath(__file__))

# For rw data
WORKSPACE = DATA_PATH = os.path.join(os.path.expanduser('~'), '.libvirt-ci')

# For testing running
RUNTEST_PATH = os.path.join('/var/tmp/libvirt-ci', 'runtest')

# For Enviroment Monitoring
ENV_PATH = os.path.join(DATA_PATH, 'env')

# For git repos
REPO_PATH = os.path.join(DATA_PATH, 'repo')

# Path to store key for ansible to use
KEY_PATH = os.path.join(DATA_PATH, 'keys')

# For SELinux rules
SEL_PATH = os.path.join(DATA_PATH, 'selinux')

# Path to store key for ansible to use
CERT_PATH = os.path.join(RESOURCE_PATH, 'certs')


# pylint: disable=too-few-public-methods
def setup_data_dir():
    """
    Copy needed data (especially ssh keys) into workspace and change permission,
    create needed folders.
    """
    for dir_ in [PATH, WORKSPACE, RUNTEST_PATH, ENV_PATH, REPO_PATH]:
        if not os.path.isdir(dir_):
            os.makedirs(dir_)

    if not os.path.isdir(KEY_PATH):
        shutil.copytree(os.path.join(PATH, 'keys'), KEY_PATH)
        for key in os.listdir(KEY_PATH):
            if os.path.isfile(os.path.join(KEY_PATH, key)):
                os.chmod(os.path.join(KEY_PATH, key), 384)  # 0600

    if not os.path.isdir(SEL_PATH):
        shutil.copytree(os.path.join(PATH, 'selinux'), SEL_PATH)
        for rule in os.listdir(SEL_PATH):
            if os.path.isfile(os.path.join(SEL_PATH, rule)):
                os.chmod(os.path.join(SEL_PATH, rule), 384)  # 0600
