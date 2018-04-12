"""
Library for installing required packages dynamically
"""

import logging
import sys
import pip

LOGGER = logging.getLogger(__name__)

OSP_LOCKED_PACKAGES = [
    'oslo.config==4.2.0',
    'oslo.utils==3.25.1',
    'oslo.i18n==3.15.3',
    'oslo.serialization==2.18.0',
]

PIP_PACKAGE_INFO = {
    # TODO: Clean up
    'ansible': 'ansible>=2.1,<2.4',
    'oauth2client': ['requests==2.14.2', 'oauth2client'],
    'gspread': ['requests==2.14.2', 'gspread==0.6.2'],
    'bkr': ['requests==2.14.2', 'beaker-client==24.2'],
    'sphinxcontrib-programoutput': ['Babel==2.3.4', 'sphinxcontrib-programoutput==0.11'],
    'sphinx-argparse': ['requests==2.14.2', 'Babel==2.3.4', 'sphinx-argparse==0.2.2'],
    'sphinx': ['requests==2.14.2', 'Babel==2.3.4', 'sphinx==1.7.1'],
    'krbV': 'python-krbV',
    'dateutil': 'python-dateutil',
    'git': 'GitPython',
    'jenkins': 'python-jenkins',
    # This is required by latest jenkins-job-builder
    # Or there'll be a version conflict when installing JJB
    'jinja2': 'jinja2<2.9',
    'stomp': 'stomp.py',
    'yaml': 'PyYAML',
    'Levenshtein': 'python-Levenshtein',
    'psycopg2': 'psycopg2<2.7',
    'novaclient': OSP_LOCKED_PACKAGES + ['Babel==2.3.4', 'python-novaclient==7.1.0'],
    'glanceclient': OSP_LOCKED_PACKAGES + ['Babel==2.3.4', 'python-glanceclient==2.6.0'],
    'keystoneclient': OSP_LOCKED_PACKAGES + ['Babel==2.3.4', 'python-keystoneclient==3.10.0'],
    'neutronclient': OSP_LOCKED_PACKAGES + ['Babel==2.3.4', 'python-neutronclient==6.2.0'],
    'requests': 'requests==2.14.2',
    'sphinxcontrib-confluencebuilder': 'sphinxcontrib-confluencebuilder==0.8',
}


def install_pip_package(pkg_name, extra_cmd=None):
    extra_cmd = extra_cmd or []
    if pkg_name in PIP_PACKAGE_INFO:
        pkg_name = PIP_PACKAGE_INFO[pkg_name]
    if not isinstance(pkg_name, list):
        pkg_name = [pkg_name]
    pip.main(['install', '--use-wheel'] + pkg_name + extra_cmd)


def install_requirements(requirements):
    for package in requirements:
        install_options = None
        if isinstance(requirements, dict):
            install_options = requirements[package]

        extra_cmd = []
        if install_options:
            for key, value in install_options.items():
                extra_cmd += ['--%s' % key, value]
            LOGGER.info("Installing pip package %s (extra command: %s)",
                        package, ' '.join(extra_cmd))
        else:
            LOGGER.info("Installing pip package %s", package)
        install_pip_package(package, extra_cmd)


def import_module(mod_name):
    try:
        import importlib
    except ImportError:
        # Python 2.6 doesn't provide importlib
        LOGGER.info("installing importlib")
        pip.main(['install', '--use-wheel', 'importlib'])
        import importlib

    old_mods = sys.modules.keys()

    imported_mod = None
    last_missing_package = None
    while True:
        try:
            imported_mod = importlib.import_module(mod_name)
            break
        except ImportError as details:
            message = str(details.message)
            if not message.startswith('No module'):
                raise

            missing_module = message.split()[-1]
            missing_package = missing_module.split('.')[0]
            if last_missing_package == missing_package:
                raise ImportError("Importing module %s failed: %s" %
                                  (missing_package, details))
            last_missing_package = missing_package
            LOGGER.info("Installing missing package %s for module %s",
                        missing_package, mod_name)
            install_pip_package(missing_package)

    new_mods = set(sys.modules.keys()) - set(old_mods)

    # Find modules who specified requirements and install them
    for key in new_mods:
        submod = sys.modules[key]
        if hasattr(submod, 'REQUIREMENTS'):
            install_requirements(submod.REQUIREMENTS)

    return imported_mod
