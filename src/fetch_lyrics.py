import asyncio
import aiohttp
import logging
from sqlalchemy.orm import scoped_session
from sqlalchemy import select
from ktv_extractor import model
from ktv_extractor.model import Song
from ktv_extractor.lyrics.match import match_lyrics
from ktv_extractor.lyrics.provider.qm import QQMusicLyricsProvider
from ktv_extractor.lyrics.provider.ne import NeteaseMusicLyricsProvider
from ktv_extractor.lyrics.provider.kg import KugouLyricsProvider
from ktv_extractor.lyrics.enum import LyricsFormat
from ktv_extractor.lyrics.converter import convert2

logging.basicConfig(level=logging.INFO)

model.init()

async def main():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(10)) as session:
        providers = [
            QQMusicLyricsProvider(session),
            KugouLyricsProvider(session),
            NeteaseMusicLyricsProvider(session),
        ]
        songs: list[model.Song]
        with scoped_session(model.session_factory)() as session:
            songs = session.scalars(select(Song).where(Song.lrc_path == None).order_by(Song.lrc_fails)).all()
            for song in songs:
                found = False
                for provider in providers:
                    try:
                        lyrics = await match_lyrics(provider, song)
                        if lyrics:
                            found = True
                            try:
                                converted = convert2(lyrics, ['orig'], LyricsFormat.VERBATIMLRC)
                                lrc_path = '.'.join([*song.path.split('.')[:-1], 'lrc'])
                                print(lrc_path)
                                with open(lrc_path, 'w', encoding='utf-8') as f:
                                    f.write(converted)
                                song.lrc_path = lrc_path
                                session.commit()
                                logging.info(f'{provider.__class__.__name__}已生成歌词：{lrc_path}')
                                break
                            except Exception as ex:
                                logging.error(f'生成LRC失败：{ex}', exc_info=ex, stack_info=True)
                    except Exception as ex:
                        logging.error(f'{provider.__class__.__name__}匹配歌词失败：{ex}')
                if not found:
                    song.lrc_fails += 1
                    session.commit()
                    logging.info(f'没有找到歌词：{song.id} {song.name}')

asyncio.run(main())