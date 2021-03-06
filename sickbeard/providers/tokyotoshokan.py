#
# This file is part of SickGear.
#
# SickGear is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickGear is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickGear.  If not, see <http://www.gnu.org/licenses/>.

import re
import time
import urllib

from . import generic
from sickbeard import show_name_helpers, tvcache
from sickbeard.helpers import tryInt
from sickbeard.bs4_parser import BS4Parser


class TokyoToshokanProvider(generic.TorrentProvider):

    def __init__(self):
        generic.TorrentProvider.__init__(self, 'TokyoToshokan', anime_only=True)

        self.url_base = self.url = 'https://tokyotosho.info/'

        self.cache = TokyoToshokanCache(self)

    def _search_provider(self, search_params, **kwargs):

        results = []
        if self.show and not self.show.is_anime:
            return results

        items = {'Season': [], 'Episode': [], 'Propers': []}

        rc = dict((k, re.compile('(?i)' + v)) for (k, v) in {
            'nodots': r'[\.\s]+', 'stats': r'S:\s*?(\d)+\s*L:\s*(\d+)', 'size': r'size:\s*(\d+[.,]\d+\w+)'}.iteritems())

        for mode in search_params.keys():
            for search_string in search_params[mode]:
                params = urllib.urlencode({'terms': rc['nodots'].sub(' ', search_string).encode('utf-8'), 'type': 1})

                search_url = '%ssearch.php?%s' % (self.url, params)

                html = self.get_url(search_url)
                if self.should_skip():
                    return self._sort_seeding(mode, results)

                cnt = len(items[mode])
                try:
                    if not html or self._has_no_results(html):
                        raise generic.HaltParseException

                    with BS4Parser(html, features=['html5lib', 'permissive']) as soup:
                        torrent_table = soup.find('table', class_='listing')
                        torrent_rows = [] if not torrent_table else torrent_table.find_all('tr')
                        if torrent_rows:
                            a = (0, 1)[None is not torrent_rows[0].find('td', class_='centertext')]

                            for top, bottom in zip(torrent_rows[a::2], torrent_rows[a+1::2]):
                                try:
                                    bottom_text = bottom.get_text() or ''
                                    stats = rc['stats'].findall(bottom_text)
                                    seeders, leechers = (0, 0) if not stats else [tryInt(n) for n in stats[0]]

                                    size = rc['size'].findall(bottom_text)
                                    size = size and size[0] or -1

                                    info = top.find('td', class_='desc-top')
                                    title = info and re.sub(r'[ .]{2,}', '.', info.get_text().strip())
                                    links = info and map(lambda l: l.get('href', ''), info.find_all('a')) or None
                                    download_url = self._link(
                                        (filter(lambda l: 'magnet:' in l, links)
                                         or filter(lambda l: not re.search(r'(magnet:|\.se).+', l), links))[0])
                                except (AttributeError, TypeError, ValueError, IndexError):
                                    continue

                                if title and download_url:
                                    items[mode].append((title, download_url, seeders, self._bytesizer(size)))

                except (StandardError, Exception):
                    time.sleep(1.1)

                self._log_search(mode, len(items[mode]) - cnt, search_url)

            results = self._sort_seeding(mode, results + items[mode])

        return results

    def _season_strings(self, *args, **kwargs):
        return [{'Season': show_name_helpers.makeSceneSeasonSearchString(self.show, *args)}]

    def _episode_strings(self, *args, **kwargs):
        return [{'Episode': show_name_helpers.makeSceneSearchString(self.show, *args)}]


class TokyoToshokanCache(tvcache.TVCache):

    def __init__(self, this_provider):
        tvcache.TVCache.__init__(self, this_provider)

        self.update_freq = 15

    def _cache_data(self, **kwargs):

        mode = 'Cache'
        search_url = '%srss.php?%s' % (self.provider.url, urllib.urlencode({'filter': '1'}))
        data = self.get_rss(search_url)

        results = []
        if data and 'entries' in data:

            rc = dict((k, re.compile('(?i)' + v)) for (k, v) in {'size': r'size:\s*(\d+[.,]\d+\w+)'}.iteritems())

            for cur_item in data.get('entries', []):
                try:
                    title, download_url = self._title_and_url(cur_item)
                    size = rc['size'].findall(cur_item.get('summary_detail', {'value': ''}).get('value', ''))
                    size = size and size[0] or -1

                except (AttributeError, TypeError, ValueError):
                    continue

                if title and download_url:
                    # feed does not carry seed, leech counts
                    results.append((title, download_url, 0, self.provider._bytesizer(size)))

        self.provider._log_search(mode, len(results), search_url)

        return results


provider = TokyoToshokanProvider()
