import random
import re
import json
import logging
from base64 import b64decode
from .. import BaseLyricsProvider, SearchType, LyricsLine, LyricsData, MultiLyricsData, LyricsWord
from ..enum import Source
from ..decryptor import krc_decrypt

logger = logging.getLogger(__name__)

class KugouLyricsProvider(BaseLyricsProvider):
    async def search(self, keyword, search_type, info = None, page = 1):
        domain = random.choice(["mobiles.kugou.com", "msearchcdn.kugou.com", "mobilecdnbj.kugou.com", "msearch.kugou.com"])  # noqa: S311

        match search_type:
            case SearchType.SONG:
                url = f"http://{domain}/api/v3/search/song"
                params = {
                    "showtype": "14",
                    "highlight": "",
                    "pagesize": "30",
                    "tag_aggr": "1",
                    "tagtype": "全部",
                    "plat": "0",
                    "sver": "5",
                    "keyword": keyword,
                    "correct": "1",
                    "api_ver": "1",
                    "version": "9108",
                    "page": page,
                    "area_code": "1",
                    "tag": "1",
                    "with_res_tag": "1",
                }
            case SearchType.SONGLIST:
                url = f"http://{domain}/api/v3/search/special"
                params = {
                    "version": "9108",
                    "highlight": "",
                    "keyword": keyword,
                    "pagesize": "20",
                    "filter": "0",
                    "page": page,
                    "sver": "2",
                    "with_res_tag": "1",
                }
            case SearchType.ALBUM:
                url = f"http://{domain}/api/v3/search/album"
                params = {
                    "version": "9108",
                    "iscorrection": "1",
                    "highlight": "",
                    "plat": "0",
                    "keyword": keyword,
                    "pagesize": "20",
                    "page": page,
                    "sver": "2",
                    "with_res_tag": "1",
                }
            case SearchType.LYRICS:
                if not info:
                    msg = "错误: 缺少参数info"
                    raise ValueError(msg)
                url = "http://lyrics.kugou.com/search"
                params = {
                    "ver": 1,
                    "man": "yes",
                    "client": "pc",
                    "keyword": keyword,
                    "duration": info["duration"],
                    "hash": info["hash"],
                }
            case _:
                msg = f"错误: 未知搜索类型{search_type!s}"
                raise ValueError(msg)
        async with self.client_session.get(url, params=params) as response:
            response.raise_for_status()
            if search_type == SearchType.LYRICS:
                response_json = await response.json()
            else:
                response_json = json.loads(re.findall(r"<!--KG_TAG_RES_START-->(.*)<!--KG_TAG_RES_END-->", await response.text(), re.DOTALL)[0])
            match search_type:
                case SearchType.SONG:
                    results = kgsonglist2result(response_json['data']['info'])
                case SearchType.SONGLIST:
                    results = []
                    for songlist in response_json['data']['info']:
                        results.append({
                            'id': songlist['specialid'],
                            'name': songlist['specialname'],
                            'pic': songlist['imgurl'],  # 歌单封面
                            'count': songlist['songcount'],  # 歌曲数量
                            'time': songlist['publishtime'],
                            'creator': songlist['nickname'],
                            'source': Source.KG,
                        })
                case SearchType.ALBUM:
                    results = []
                    for album in response_json['data']['info']:
                        results.append({
                            'id': album['albumid'],
                            'name': album['albumname'],
                            'pic': album['imgurl'],  # 专辑封面
                            'count': album['songcount'],  # 歌曲数量
                            'time': album['publishtime'],
                            'artist': album['singername'],
                            'source': Source.KG,
                        })
                case SearchType.LYRICS:
                    results = []
                    for lyric in response_json['candidates']:
                        results.append({
                            "id": lyric['id'],
                            "accesskey": lyric['accesskey'],
                            "duration": lyric['duration'],
                            "creator": lyric['nickname'],
                            "score": lyric['score'],
                            "source": Source.KG,
                        })
            logger.debug("搜索结果：%s", json.dumps(results, default=lambda x: str(x), ensure_ascii=False, indent=4))
            if search_type == SearchType.LYRICS:
                results = [{**info, **item, "duration": info['duration']} for item in results]
            return results
    
    async def get_lyrics(self, lyrics):
        if not lyrics.id or not lyrics.accesskey:
            return
        url = "https://lyrics.kugou.com/download"
        params = {
            "ver": 1,
            "client": "pc",
            "id": lyrics.id,
            "accesskey": lyrics.accesskey,
            "fmt": "krc",
            "charset": "utf8",
        }
        async with self.client_session.get(url, params=params) as response:
            response.raise_for_status()
            response_json = await response.json()
            encrypted_krc = b64decode(response_json['content'])
            lyrics.tags, lyric = krc2dict(krc_decrypt(encrypted_krc))
            lyrics.update(lyric)

def kgsonglist2result(songlist: list, list_type: str = "search") -> list:
    results = []

    for song in songlist:
        match list_type:
            case "songlist":
                title = song['filename'].split("-")[1].strip()
                artist = song['filename'].split("-")[0].strip().split("、")
                album = ""
            case "search":
                title = song['songname']
                album = song['album_name']
                artist = song['singername'].split("、")
        results.append({
            'hash': song['hash'],
            'title': title,
            'subtitle': "",
            'duration': song['duration'],
            'artist': artist,
            'album': album,
            'language': song['trans_param'].get('language', ''),
            'source': Source.KG,
        })
    return results

def krc2dict(krc: str) -> tuple[dict, dict]:
    """将明文krc转换为字典{歌词类型: [(行起始时间, 行结束时间, [(字起始时间, 字结束时间, 字内容)])]}."""
    lrc_dict = MultiLyricsData({})
    tag_split_pattern = re.compile(r"^\[(\w+):([^\]]*)\]$")
    tags: dict[str, str] = {}

    line_split_pattern = re.compile(r'^\[(\d+),(\d+)\](.*)$')  # 逐行匹配
    wrods_split_pattern = re.compile(r'(?:\[\d+,\d+\])?<(\d+),(\d+),\d+>((?:.(?!\d+,\d+,\d+>))*)')  # 逐字匹配
    orig_list = LyricsData([])  # 原文歌词
    roma_list = LyricsData([])
    ts_list = LyricsData([])

    for i in krc.splitlines():
        line = i.strip()
        if not line.startswith("["):
            continue

        tag_split_content = re.findall(tag_split_pattern, line)
        if tag_split_content:  # 标签行
            tags.update({tag_split_content[0][0]: tag_split_content[0][1]})
            continue

        line_split_content = re.findall(line_split_pattern, line)
        if not line_split_content:
            continue
        line_start_time, line_duration, line_content = line_split_content[0]
        orig_list.append(LyricsLine((int(line_start_time), int(line_start_time) + int(line_duration), [])))

        wrods_split_content = re.findall(wrods_split_pattern, line_content)
        if not wrods_split_content:
            orig_list[-1][2].append(LyricsWord((int(line_start_time), int(line_start_time) + int(line_duration), line_content)))
            continue

        for word_start_time, word_duration, word_content in wrods_split_content:
            orig_list[-1][2].append(LyricsWord((int(line_start_time) + int(word_start_time),
                                    int(line_start_time) + int(word_start_time) + int(word_duration), word_content)))

    if "language" in tags and tags["language"].strip() != "":
        languages = json.loads(b64decode(tags["language"].strip()))
        for language in languages["content"]:
            if language["type"] == 0:  # 逐字(罗马音)
                offset = 0  # 用于跳过一些没有内容的行,它们不会存在与罗马音的字典中
                for i, line in enumerate(orig_list):
                    if "".join([w[2] for w in line[2]]) == "":
                        # 如果该行没有内容,则跳过
                        offset += 1
                        continue

                    roma_line = (line[0], line[1], [])
                    for j, word in enumerate(line[2]):
                        roma_line[2].append((word[0], word[1], language["lyricContent"][i - offset][j]))
                    roma_list.append(LyricsLine(roma_line))
            elif language["type"] == 1:  # 逐行(翻译)
                for i, line in enumerate(orig_list):
                    ts_list.append(LyricsLine((line[0], line[1], [LyricsWord((line[0], line[1], language["lyricContent"][i][0]))])))

    tags_str = ""
    for key, value in tags.items():
        if key in ["al", "ar", "au", "by", "offset", "ti"]:
            tags_str += f"[{key}:{value}]\n"

    for key, lrc_list in ({"orig": orig_list, "roma": roma_list, "ts": ts_list}).items():
        if lrc_list:
            lrc_dict[key] = lrc_list
    return tags, lrc_dict
