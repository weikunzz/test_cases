"""
Runner module for libvirt-test-API test framework
"""
import logging
import os
import re
import string
import yaml
import socket

from .. import config
from .. import metadata

from . import test_api

LOGGER = logging.getLogger(__name__)


class InstallRunner(test_api.TestApiRunner):
    """
    Runner for libvirt-test-API installation test framework
    """

    repos = {
        "test-api":
            'http://git.host.prod.eng.bos.redhat.com/git/libvirt-test-API.git rhel7',
    }

    # pylint: disable=no-self-use
    def list_tests(self):
        """
        Get all specific type tests in libvirt-test-API.
        """
        old_path = os.getcwd()
        try:
            os.chdir(self.working_dir)
            tests = []
            for file_name in os.listdir('templates'):
                if file_name.endswith('conf'):
                    file_name = file_name[:-5]
                    if re.search(r"domain_.*_inst", file_name):
                        if (not self.params.inst_guest_list or
                                not self.params.inst_arch_list):
                            LOGGER.error("No parameters found for inst_guest_list"
                                         " or inst_arch_list")
                            continue
                        for guestos in self.params.inst_guest_list.split():
                            for guestarch in self.params.inst_arch_list.split():
                                if (guestos.startswith("rhel7") and guestarch == 'i386') or (guestos.startswith("rhel6") and guestarch == 'ppc64le'):
                                    continue
                                tests.append("%s.GUESTOS_%s.GUESTARCH_%s" %
                                             (file_name, guestos, guestarch))
                    else:
                        tests.append(file_name)
            return tests
        finally:
            os.chdir(old_path)

    def prepare_test(self, test_name):
        """
        Action to perform before a test case
        """
        # pylint: disable=unused-variable
        test = test_name
        params_path = os.path.join(config.PATH, 'test_api_params.yaml')
        with open(params_path) as param_fp:
            all_params = yaml.load(param_fp)

        params = all_params['defaults']
        for override in all_params['overrides']:
            # pylint: disable=unused-variable,eval-used
            # Prepare variables for eval
            info = self  # noqa
            if eval(override['when']):
                for key, value in override.items():
                    if key != 'when':
                        params[key] = value

        # Substitute $ENV_NAME or ${ENV_NAME} to ENV_VALUE
        for key, value in params.items():
            params[key] = string.Template(value).safe_substitute(os.environ)

        if '.' in test_name:
            test_name, test_matrix = test_name.split('.', 1)
        else:
            test_name, test_matrix = test_name, None
        case_str = []
        template_path = os.path.join(self.working_dir, 'templates',
                                     test_name + '.conf')

        if 'PRODUCT_DATA' not in os.environ:
            product_data = metadata.Metadata('Products').fetch()
            os.environ['PRODUCT_DATA'] = yaml.dump(product_data)
        else:
            product_data = yaml.load(os.environ['PRODUCT_DATA'])

        location = socket.gethostname()
        if "pek2" in location:
            download_url = "http://download.eng.pek2.redhat.com/pub/rhel/rel-eng/"
        else:
            download_url = "http://download.eng.bos.redhat.com/rel-eng/"

        with open(template_path) as template_fp:
            lines = template_fp.read()
            if test_matrix:
                for replace in test_matrix.split('.'):
                    key, value = replace.split('_', 1)
                    # Get newest RHEL repo
                    if "GUESTOS" in key and "rhel" in value:
                        temp = value.upper()
                        version = temp.replace('U', '.')
                        if version in product_data.keys():
                            tree = product_data[version]['Tree Repo Name']
                            prodlist = ['RHEL', 'RHEL-ALT']
                            if any(i for i in prodlist if i in tree):
                                params['RHEL_NEWEST'] = (download_url + tree + "/compose/Server/")

                    lines = re.sub("#%s#" % key, value, lines)
            else:
                params["RHEL_NEWEST"] = ""
                prefix = ""
                if "6_latest" in test_name:
                    prefix = "RHEL6"
                elif "7_latest" in test_name:
                    prefix = "RHEL7"
                elif "rhel_alt_latest" in test_name:
                    prefix = "RHEL-ALT7"

                if prefix:
                    minors = []
                    for product in product_data.keys():
                        if product.startswith(prefix):
                            _, minor = product.split('.')
                            minors.append(int(minor))
                    tree = product_data[prefix + '.' + str(max(minors))]['Tree Repo Name']
                    if prefix.startswith('RHEL-ALT'):
                        params['RHEL_ALT_NEWEST'] = (download_url + tree + "/compose/Server/")
                    elif prefix.startswith('RHEL'):
                        params['RHEL_NEWEST'] = (download_url + tree + "/compose/Server/")

            for line in lines.splitlines():
                result = re.findall(r'#([_A-Z]+)#', line)
                if result:
                    for placeholder in result:
                        line = re.sub(
                            '#%s#' % placeholder,
                            params[placeholder], line)
                case_str.append(line)

        case_conf_path = os.path.join(self.working_dir, 'case.conf')
        with open(case_conf_path, 'w') as conf_fp:
            conf_fp.write('\n'.join(case_str))
