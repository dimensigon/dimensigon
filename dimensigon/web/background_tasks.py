import logging
import typing as t

from pkg_resources import parse_version

import dimensigon.use_cases.routing as routing
import dimensigon.web.network as ntwrk
from dimensigon import __version__ as dm_version
from dimensigon.domain.entities import Server
from dimensigon.web import get_root_auth
from dimensigon.use_cases.use_cases import run_elevator, get_software
from dimensigon.utils import asyncio
from dimensigon.web.decorators import run_as

logger = logging.getLogger('dm.background')
catalog_logger = logging.getLogger('dm.catalog')
upgrader_logger = logging.getLogger('dm.upgrader')


#
# @run_as('root')
# def process_get_new_version_from_gogs(app=None):
#     """
#     checks if new version in repo
#
#     Parameters
#     ----------
#     app:
#         app to load the context
#     timeout_wait_transfer:
#         timeout waiting tranfer file to end.
#     refresh_interval:
#         time period to check if tranfer ended. Normally, used for test purposes
#
#     Returns
#     -------
#
#     """
#     upgrader_logger.info('Starting Upgrade Process')
#     base_url = os.environ.get('GIT_REPO') \
#                or current_app.config.get('GIT_REPO') \
#                or 'https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000'
#     releases_uri = '/dimensigon/dimensigon/releases'
#     try:
#         r = requests.get(base_url + releases_uri, verify=current_app.config['SSL_VERIFY'], timeout=10)
#     except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
#         r = None
#         upgrader_logger.info('Unable to contact to main repo')
#
#     # get new versions from repo
#     if r and r.status_code == 200:
#         # get current software
#         gogs_versions = {}
#
#         html_content = r.text
#         soup = BeautifulSoup(html_content, 'html.parser')
#         for li in soup.find(id='release-list').find_all('li'):
#             version = li.h4.a.get_text(strip=True)
#             uris = [a.attrs['href'] for a in li.find('div', class_='download').find_all('a') if
#                     a.attrs['href'].endswith('tar.gz')]
#             if len(uris) > 0:
#                 gogs_versions.update({parse_version(version): uris[0]})
#         current_version = parse_version(dm_version)
#         new_versions = [gogs_ver for gogs_ver in gogs_versions if gogs_ver > current_version]
#
#         if new_versions:
#             new_version = max(new_versions)
#             upgrader_logger.info(f"Downloading version {new_version} from outside world")
#
#             r = requests.get(base_url + gogs_versions[new_version],
#                              verify=current_app.config['SSL_VERIFY'])
#             filename = get_filename_from_cd(
#                 r.headers.get(
#                     'content-disposition')) or f"dimensigon-{gogs_versions[new_version].rsplit('/', 1)[-1]}"
#             os.makedirs(os.path.join(current_app.config['SOFTWARE_REPO'], 'dimensigon'), exist_ok=True)
#             file = os.path.join(current_app.config['SOFTWARE_REPO'], 'dimensigon', filename)
#             try:
#                 open(file, 'wb').write(r.content)
#             except Exception as e:
#                 upgrader_logger.exception(f"Unable to save {file}")
#             else:
#                 run_elevator(file, new_version, upgrader_logger)
#     else:
#         upgrader_logger.debug(f"No version to upgrade")


def upgrade_version(data: t.Dict[Server, ntwrk.Response]):
    mayor_version, mayor_server = None, None
    for server, response in data.items():
        if response.code == 200 and 'version' in response.msg:
            remote_version = parse_version(response.msg['version'])
            if remote_version > parse_version(dm_version):
                if mayor_version is None or mayor_version < remote_version:
                    mayor_version, mayor_server = remote_version, server
    if mayor_version:
        catalog_logger.info(f'Found mayor version on server {mayor_server}. Upgrading version first')
        file, v = get_software(mayor_server, get_root_auth())
        if file:
            run_elevator(file, mayor_version, catalog_logger)
            return True
    return False


@run_as('root')  # takes the app argument and pushes the context
def process_catalog_route_table(app=None, upgrade_catalog=True):
    # app will be used for the run_as decorator
    from dimensigon.web.api_1_0.urls.use_cases import delete_old_temp_servers
    delete_old_temp_servers()
    asyncio.run(routing.async_update_routes_send(discover_new_neighbours=True, check_current_neighbours=True,
                                                 max_num_discovery=3))
