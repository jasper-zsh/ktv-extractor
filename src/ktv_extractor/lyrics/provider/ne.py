import logging
import json
import time
import random
import re
from .. import BaseLyricsProvider, SearchType, LyricsData, LyricsLine, LyricsWord
from ..enum import Source
from ..decryptor.eapi import eapi_params_decrypt, eapi_params_encrypt, eapi_response_decrypt
from . import lrc2list, plaintext2list

logger = logging.getLogger(__name__)

NeteaseCloudMusic_headers = {
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded",
    "MG-Product-Name": "music",
    "Nm-GCore-Status": "1",
    "Origin": "orpheus://orpheus",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)"
                  " Chrome/35.0.1916.157 NeteaseMusicDesktop/2.9.7.199711 Safari/537.36",
    "Accept-Encoding": "gzip,deflate",
    "Accept-Language": "en-us,en;q=0.8",
    "Cookie": "os=pc; osver=Microsoft-Windows-10--build-22621-64bit; appver=2.9.7.199711; channel=netease; WEVNSM=1.0.0; WNMCID=slodmo.1709434129796.01.0;",
}

class NeteaseMusicLyricsProvider(BaseLyricsProvider):
    async def search(self, keyword, search_type, page = 1):
        match search_type:
            case SearchType.SONG:
                param_type = "1"
            case SearchType.ALBUM:
                param_type = "10"
            case SearchType.ARTIST:
                param_type = "100"
            case SearchType.SONGLIST:
                param_type = "1000"
            case SearchType.LYRICS:
                param_type = "1006"

        params = {
            "hlpretag": '<span class="s-fc2">',
            "hlposttag": "</span>",
            "type": param_type,
            "queryCorrect": "true",
            "s": keyword,
            "offset": str((int(page) - 1) * 20),
            "total": "true",
            "limit": "20",
            "e_r": True,
            "header": eapi_get_params_header(),
        }
        data = await self._eapi_request("/eapi/cloudsearch/pc", params)
        if 'result' not in data:
            return []
        match search_type:
            case SearchType.SONG:
                if 'songs' not in data['result']:
                    return []
                results = self.nesonglist2result(data['result']['songs'])
            case SearchType.ALBUM:
                if 'albums' not in data['result']:
                    return []
                results = []
                for album in data['result']['albums']:
                    results.append({
                        'id': album['id'],
                        'name': album['name'],
                        'pic': album['picUrl'],  # 专辑封面
                        'count': album['size'],  # 歌曲数量
                        'time': time.strftime('%Y-%m-%d', time.localtime(album['publishTime'] // 1000)),
                        'artist': album['artists'][0]["name"] if album['artists'] else "",
                        'source': Source.NE,
                    })
            case SearchType.SONGLIST:
                if 'playlists' not in data['result']:
                    return []
                results = []
                for songlist in data['result']['playlists']:
                    results.append({
                        'id': songlist['id'],
                        'name': songlist['name'],
                        'pic': songlist['coverImgUrl'],  # 歌单封面
                        'count': songlist['trackCount'],  # 歌曲数量
                        'time': "",
                        'creator': songlist['creator']['nickname'],
                        'source': Source.NE,
                    })
        logger.info("搜索成功")
        logger.debug("搜索结果: %s", json.dumps(results, default=lambda x: str(x), ensure_ascii=False, indent=4))
        return results
    
    async def get_lyrics(self, lyrics):
        if lyrics.id is None:
            msg = "Lyrics id is None"
            raise Exception(msg)
        params = {
            "os": "pc",
            "id": str(lyrics.id),
            "lv": "-1",
            "kv": "-1",
            "tv": "-1",
            "rv": "-1",
            "yv": "1",
            "showRole": "true",
            "cp": "true",
            "e_r": True,
        }
        response = await self._eapi_request("/eapi/song/lyric", params)
        tags = {}
        if lyrics.artist:
            tags.update({"ar": "/".join(lyrics.artist) if isinstance(lyrics.artist, list) else lyrics.artist})
        if lyrics.album:
            tags.update({"al": lyrics.album})
        if lyrics.title:
            tags.update({"ti": lyrics.title})
        if 'lyricUser' in response and 'nickname' in response['lyricUser']:
            tags.update({"by": response['lyricUser']['nickname']})
        if 'transUser' in response and 'nickname' in response['transUser']:
            if 'by' in tags and tags['by'] != response['transUser']['nickname']:
                tags['by'] += f" & {response['transUser']['nickname']}"
            elif 'by' not in tags:
                tags.update({"by": response['transUser']['nickname']})
        lyrics.tags = tags
        if 'yrc' in response and len(response['yrc']['lyric']) != 0:
            mapping_table = [("orig", 'yrc'),
                            ("ts", 'tlyric'),
                            ("roma", 'romalrc'),
                            ("orig_lrc", 'lrc')]
        else:
            mapping_table = [("orig", 'lrc'),
                            ("ts", 'tlyric'),
                            ("roma", 'romalrc')]
        for key, value in mapping_table:
            if value not in response:
                continue
            if isinstance(response[value]['lyric'], str) and len(response[value]['lyric']) != 0:
                if value == 'yrc':
                    lyrics[key] = yrc2list(response[value]['lyric'])
                elif "[" in response[value]['lyric'] and "]" in response[value]['lyric']:
                    lyrics[key] = lrc2list(response[value]['lyric'], source=Source.NE)[1]
                else:
                    lyrics[key] = plaintext2list(response[value]['lyric'])

    
    def nesonglist2result(self, songlist: list) -> list:
        results = []
        for song in songlist:
            info = song
            # 处理艺术家
            artist = [singer['name'] for singer in info['ar'] if singer['name'] != ""]
            results.append({
                'id': info['id'],
                'title': info['name'],
                'subtitle': info['alia'][0] if info['alia'] else "",
                'artist': artist,
                'album': info['al']['name'],
                'duration': round(info['dt'] / 1000),
                'source': Source.NE,
            })
        return results
    
    async def _eapi_request(self, path: str, params: dict) -> dict:
        """eapi接口请求

        :param path: 请求的路径
        :param params: 请求参数
        :param method: 请求方法
        :return dict: 请求结果
        """
        encrypted_params = eapi_params_encrypt(path.replace("eapi", "api").encode(), params)
        headers = NeteaseCloudMusic_headers.copy()
        # headers.update({"Content-Length": str(len(params))})
        url = "https://music.163.com" + path
        async with self.client_session.post(url, headers=headers, data=encrypted_params) as response:
            response.raise_for_status()
            data = eapi_response_decrypt(await response.content.read())
            return json.loads(data)


    

def eapi_get_params_header() -> str:
    return json.dumps({
        "os": "pc",
        "appver": "2.9.7.199711",
        "deviceId": "",
        "requestId": str(random.randint(10000000, 99999999)),  # noqa: S311
        "clientSign": "",
        "osver": "Microsoft-Windows-10--build-22621-64bit",
        "Nm-GCore-Status": "1",
    }, ensure_ascii=False, separators=(',', ':'))


def yrc2list(yrc: str) -> list:
    """将yrc转换为列表[(行起始时间, 行结束时间, [(字起始时间, 字结束时间, 字内容)])]"""
    lrc_list = LyricsData([])

    line_split_pattern = re.compile(r'^\[(\d+),(\d+)\](.*)$')  # 逐行匹配
    wrods_split_pattern = re.compile(r'(?:\[\d+,\d+\])?\((\d+),(\d+),\d+\)((?:.(?!\d+,\d+,\d+\)))*)')  # 逐字匹配
    for i in yrc.splitlines():
        line = i.strip()
        if not line.startswith("["):
            continue

        line_split_content = re.findall(line_split_pattern, line)
        if not line_split_content:
            continue
        line_start_time, line_duration, line_content = line_split_content[0]
        lrc_list.append(LyricsLine((int(line_start_time), int(line_start_time) + int(line_duration), [])))

        wrods_split_content = re.findall(wrods_split_pattern, line_content)
        if not wrods_split_content:
            lrc_list[-1][2].append(LyricsWord((int(line_start_time), int(line_start_time) + int(line_duration), line_content)))
            continue

        for word_start_time, word_duration, word_content in wrods_split_content:
            lrc_list[-1][2].append(LyricsWord((int(word_start_time), int(word_start_time) + int(word_duration), word_content)))

    return lrc_list
