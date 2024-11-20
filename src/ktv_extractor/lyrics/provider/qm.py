import re
import logging
import aiohttp
import json
import random
from zlib import decompress
from enum import Enum
from base64 import b64encode
from . import lrc2list, plaintext2list
from .. import BaseLyricsProvider, SearchType, Lyrics, LyricsData, LyricsLine, LyricsWord

from ..decryptor.qmc1 import qmc1_decrypt
from ..decryptor.tripledes import DECRYPT, tripledes_crypt, tripledes_key_setup

QRC_PATTERN = re.compile(r'<Lyric_1 LyricType="1" LyricContent="(?P<content>.*?)"/>', re.DOTALL)

logger = logging.getLogger(__name__)

class QrcType(Enum):
    LOCAL = 0
    CLOUD = 1


QMD_headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN",
    "User-Agent": "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; WOW64; Trident/5.0)",
}

# proxy = {
#     'proxy': 'http://http-short.xiaoxiangdaili.com:10010',
#     'proxy_auth': aiohttp.BasicAuth('1176214447346569216', '8EhGZ4sE'),
# }
proxy = {
    'proxy': 'http://http-dynamic.xiaoxiangdaili.com:10030',
    'proxy_auth': aiohttp.BasicAuth('1176215712877137920', '91IzEMXv'),
}


class QQMusicLyricsProvider(BaseLyricsProvider):
    async def search(self, keyword, search_type, page = 1):
        if search_type not in (SearchType.SONG, SearchType.ARTIST, SearchType.ALBUM, SearchType.SONGLIST):
            msg = f"搜索类型错误,类型为{search_type}"
            raise ValueError(msg)
        search_type_mapping = {
            SearchType.SONG: 0,
            SearchType.ARTIST: 1,
            SearchType.ALBUM: 2,
            SearchType.SONGLIST: 3,
            SearchType.LYRICS: 7,
        }
        data = json.dumps({
            "comm": {
                "g_tk": 997034911,
                "uin": random.randint(1000000000, 9999999999),  # noqa: S311
                "format": "json",
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "notice": 0,
                "platform": "h5",
                "needNewCode": 1,
                "ct": 23,
                "cv": 0,
            },
            "req_0": {
                "method": "DoSearchForQQMusicDesktop",
                "module": "music.search.SearchCgiService",
                "param": {
                    "num_per_page": 20,
                    "page_num": int(page),
                    "query": keyword,
                    "search_type": search_type_mapping[search_type],
                },
            },
        }, ensure_ascii=False).encode("utf-8")
        async with self.client_session.post('https://u.y.qq.com/cgi-bin/musicu.fcg', headers=QMD_headers, data=data) as response:
            response.raise_for_status()
            res_text = await response.text()
            res_data = json.loads(res_text)
            infos = res_data['req_0']['data']['body']
            results = []
            match search_type:

                case SearchType.SONG:
                    results = self.qmsonglist2result(infos['song']['list'])

                case SearchType.ALBUM:
                    for album in infos['album']['list']:
                        results.append({
                            'id': album['albumID'],
                            'mid': album['albumMID'],
                            'name': album['albumName'],
                            'pic': album['albumPic'],  # 专辑封面
                            'count': album['song_count'],  # 歌曲数量
                            'time': album['publicTime'],
                            'artist': album['singerName'],
                            'source': self,
                        })

                case SearchType.SONGLIST:
                    for songlist in infos['songlist']['list']:
                        results.append({
                            'id': songlist['dissid'],
                            'name': songlist['dissname'],
                            'pic': songlist['imgurl'],  # 歌单封面
                            'count': songlist['song_count'],  # 歌曲数量
                            'time': songlist['createtime'],
                            'creator': songlist['creator']['name'],
                            'source': self,
                        })

                case SearchType.ARTIST:
                    for artist in infos['singer']['list']:
                        results.append({
                            'id': artist['singerID'],
                            'name': artist['singerName'],
                            'pic': artist['singerPic'],  # 艺术家图片
                            'count': artist['songNum'],  # 歌曲数量
                            'source': self,
                        })
            logger.info("搜索成功")
            logger.debug("搜索结果: %s", json.dumps(results, default=lambda x: str(x), ensure_ascii=False, indent=4))
                
            return results

    async def get_lyrics(self, lyrics: Lyrics) -> None:
        if lyrics.title is None or not isinstance(lyrics.artist, list) or lyrics.album is None or not isinstance(lyrics.id, int) or lyrics.duration is None:
            msg = "缺少必要参数"
            raise Exception(msg)
        base64_album_name = b64encode(lyrics.album.encode()).decode()
        base64_singer_name = b64encode(lyrics.artist[0].encode()).decode() if lyrics.album else b64encode(b"").decode()
        base64_song_name = b64encode(lyrics.title.encode()).decode()

        data = json.dumps({
            "comm": {
                "_channelid": "0",
                "_os_version": "6.2.9200-2",
                "authst": "",
                "ct": "19",
                "cv": "1942",
                "patch": "118",
                "psrf_access_token_expiresAt": 0,
                "psrf_qqaccess_token": "",
                "psrf_qqopenid": "",
                "psrf_qqunionid": "",
                "tmeAppID": "qqmusic",
                "tmeLoginType": 0,
                "uin": "0",
                "wid": "0",
            },
            "music.musichallSong.PlayLyricInfo.GetPlayLyricInfo": {
                "method": "GetPlayLyricInfo",
                "module": "music.musichallSong.PlayLyricInfo",
                "param": {
                    "albumName": base64_album_name,
                    "crypt": 1,
                    "ct": 19,
                    "cv": 1942,
                    "interval": lyrics.duration,
                    "lrc_t": 0,
                    "qrc": 1,
                    "qrc_t": 0,
                    "roma": 1,
                    "roma_t": 0,
                    "singerName": base64_singer_name,
                    "songID": lyrics.id,
                    "songName": base64_song_name,
                    "trans": 1,
                    "trans_t": 0,
                    "type": 0,
                },
            },
        }, ensure_ascii=False).encode("utf-8")
        async with self.client_session.post('https://u.y.qq.com/cgi-bin/musicu.fcg', headers=QMD_headers, data=data) as response:
            response.raise_for_status()
            res_text = await response.text()
            response_data = json.loads(res_text)
            response_data = response_data['music.musichallSong.PlayLyricInfo.GetPlayLyricInfo']['data']
            
            for key, value in [("orig", 'lyric'),
                            ("ts", 'trans'),
                            ("roma", 'roma')]:
                lrc = response_data[value]
                lrc_t = (response_data["qrc_t"] if response_data["qrc_t"] != 0 else response_data["lrc_t"]) if value == "lyric" else response_data[value + "_t"]
                if lrc != "" and lrc_t != "0":
                    encrypted_lyric = lrc

                    lyric = qrc_decrypt(encrypted_lyric, QrcType.CLOUD)

                    if lyric is not None:
                        tags, lyric = qrc_str_parse(lyric)

                        if key == "orig":
                            lyrics.tags = tags

                        lyrics[key] = lyric
                elif (lrc_t == "0" and key == "orig"):
                    msg = "没有获取到可用的歌词"
                    raise Exception(msg)

    def qmsonglist2result(self, songlist: list, list_type: str | None = None) -> list:
        results = []
        for song in songlist:
            info = song["songInfo"] if list_type == "album" else song
            # 处理艺术家
            artist = [singer['name'] for singer in info['singer'] if singer['name'] != ""]
            results.append({
                'id': info['id'],
                'mid': info['mid'],
                'title': info['title'],
                'subtitle': info['subtitle'],
                'artist': artist,
                'album': info['album']['name'],
                'duration': info['interval'],
                'source': self,
            })
        return results

def qrc2list(s_qrc: str) -> tuple[dict, LyricsData]:
    """将qrc转换为列表[(行起始时间, 行结束时间, [(字起始时间, 字结束时间, 字内容)])]"""
    m_qrc = QRC_PATTERN.search(s_qrc)
    if not m_qrc or not m_qrc.group("content"):
        msg = "不支持的歌词格式"
        raise Exception(msg)
    qrc: str = m_qrc.group("content")
    qrc_lines = qrc.split('\n')
    tags = {}
    lrc_list = LyricsData([])
    wrods_split_pattern = re.compile(r'(?:\[\d+,\d+\])?((?:(?!\(\d+,\d+\)).)+)\((\d+),(\d+)\)')  # 逐字匹配
    line_split_pattern = re.compile(r'^\[(\d+),(\d+)\](.*)$')  # 逐行匹配
    tag_split_pattern = re.compile(r"^\[(\w+):([^\]]*)\]$")

    for i in qrc_lines:
        line = i.strip()
        line_split_content = re.findall(line_split_pattern, line)
        if line_split_content:  # 判断是否为歌词行
            line_start_time, line_duration, line_content = line_split_content[0]
            lrc_list.append(LyricsLine((int(line_start_time), int(line_start_time) + int(line_duration), [])))
            wrods_split_content = re.findall(wrods_split_pattern, line)
            if wrods_split_content:  # 判断是否为逐字歌词
                for text, starttime, duration in wrods_split_content:
                    if text != "\r":
                        lrc_list[-1][2].append(LyricsWord((int(starttime), int(starttime) + int(duration), text)))
            else:  # 如果不是逐字歌词
                lrc_list[-1][2].append(LyricsWord((int(line_start_time), int(line_start_time) + int(line_duration), line_content)))
        else:
            tag_split_content = re.findall(tag_split_pattern, line)
            if tag_split_content:
                tags.update({tag_split_content[0][0]: tag_split_content[0][1]})

    return tags, lrc_list


def qrc_str_parse(lyric: str) -> tuple[dict, LyricsData]:
    if re.search(r'<Lyric_1 LyricType="1" LyricContent="(.*?)"/>', lyric, re.DOTALL):
        return qrc2list(lyric)
    if "[" in lyric and "]" in lyric:
        try:
            return lrc2list(lyric)
        except Exception:
            logger.exception("尝试将歌词以lrc格式解析时失败,解析为纯文本")
    return {}, plaintext2list(lyric)


QRC_KEY = b"!@#)(*$%123ZXC!@!@#)(NHL"


def qrc_decrypt(encrypted_qrc: str | bytearray | bytes, qrc_type: QrcType = QrcType.CLOUD) -> str:
    if encrypted_qrc is None or encrypted_qrc.strip() == "":
        logger.error("没有可解密的数据")
        msg = "没有可解密的数据"
        raise Exception(msg)

    if isinstance(encrypted_qrc, str):
        encrypted_text_byte = bytearray.fromhex(encrypted_qrc)  # 将文本解析为字节数组
    elif isinstance(encrypted_qrc, bytearray):
        encrypted_text_byte = encrypted_qrc
    elif isinstance(encrypted_qrc, bytes):
        encrypted_text_byte = bytearray(encrypted_qrc)
    else:
        logger.error("无效的加密数据类型")
        msg = "无效的加密数据类型"
        raise Exception(msg)

    try:
        if qrc_type == QrcType.LOCAL:
            qmc1_decrypt(encrypted_text_byte)
            encrypted_text_byte = encrypted_text_byte[11:]

        data = bytearray()
        schedule = tripledes_key_setup(QRC_KEY, DECRYPT)

        # 以 8 字节为单位迭代 encrypted_text_byte
        for i in range(0, len(encrypted_text_byte), 8):
            data += tripledes_crypt(encrypted_text_byte[i:], schedule)

        decrypted_qrc = decompress(data).decode("utf-8")
    except Exception as e:
        logger.exception("解密失败")
        msg = "解密失败"
        raise Exception(msg) from e
    return decrypted_qrc
