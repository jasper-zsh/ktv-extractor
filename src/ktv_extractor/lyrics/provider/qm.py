import re
import logging
import aiohttp
import json
from zlib import decompress
from enum import Enum
from base64 import b64encode
from . import BaseLyricsProvider, lrc2list, plaintext2list
from .. import Lyrics, LyricsData, LyricsLine, LyricsWord

from ..decryptor.qmc1 import qmc1_decrypt
from ..decryptor.tripledes import DECRYPT, tripledes_crypt, tripledes_key_setup

QRC_PATTERN = re.compile(r'<Lyric_1 LyricType="1" LyricContent="(?P<content>.*?)"/>', re.DOTALL)

logger = logging.getLogger(__name__)

class QrcType(Enum):
    LOCAL = 0
    CLOUD = 1

class QQMusicLyricsProvider(BaseLyricsProvider):
    async def get_lyrics(self, lyrics: Lyrics) -> None:
        if lyrics.title is None or not isinstance(lyrics.artist, list) or lyrics.album is None or not isinstance(lyrics.id, int) or lyrics.duration is None:
            msg = "缺少必要参数"
            raise Exception(msg)
        async with aiohttp.ClientSession() as session:
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
            async with session.post('https://u.y.qq.com/cgi-bin/musicu.fcg', headers=QMD_headers, data=data, timeout=10) as response:
                response.raise_for_status()
                response_data = await response.json()
                response_data = response_data['music.musichallSong.PlayLyricInfo.GetPlayLyricInfo']['data']
                
                for key, value in [("orig", 'lyric'),
                                ("ts", 'trans'),
                                ("roma", 'roma')]:
                    lrc = response[value]
                    lrc_t = (response["qrc_t"] if response["qrc_t"] != 0 else response["lrc_t"]) if value == "lyric" else response[value + "_t"]
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
