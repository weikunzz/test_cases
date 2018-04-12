"""
Submit a xml to metadash
"""
import logging
import requests

LOGGER = logging.getLogger(__name__)


def run(params):
    metadash_url = params.url.rstrip('/')
    junit = params.junit

    fp = open(junit, 'rb')
    res = requests.post(metadash_url + '/api/testresult/xml', files={
        'file': fp
    })

    # pylint:disable=E1101
    if res.status_code != requests.codes.ok:  # noqa
        LOGGER.error('Failed submitting test run: %s', res.text)
        return 1


def parse(parser):
    """
    Parse arguments for reporting result to Jira.
    """
    parser.add_argument(
        '--metadash-url', dest='url', action='store',
        default='http://10.8.248.15/',
        help='Dashboard API URL')
    parser.add_argument(
        '--junit', dest='junit', action='store', required=True,
        help='Path of junit test result storing in')
