"""
Build name generator
"""
from libvirt_ci import package


def run(params):
    """
    Main function of name generator
    """
    try:
        print package.Package.from_name(params.label_package,
                                        host=params.host)
    except package.PackageError:
        pass


def parse(parser):
    """
    Parse arguments for name generator
    """
    parser.add_argument(
        '--label-package', dest='label_package', action='store',
        help='The label package name which used to create a build name')
    parser.add_argument(
        '--host', dest="host", action='store',
        help='Remote host name or ip')
