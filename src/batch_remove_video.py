import sqlite3
from contextlib import closing
from ktv_extractor.process import process_tracks
import asyncio
import logging

sem = asyncio.Semaphore(5)

async def process_and_update(conn: sqlite3.Connection, path: str, song_id: int):
    async with sem:
        try:
            await process_tracks(path)
            sql = 'UPDATE song SET audio_only = true WHERE id = %d' % (song_id)
            print(sql)
            conn.execute(sql)
        except Exception as ex:
            logging.error(f'处理轨道失败：{path} {ex}', exc_info=ex)
            sql = 'UPDATE song SET corrupt = true WHERE id = %d' % (song_id)
            print(sql)
            conn.execute(sql)

async def main():
    with sqlite3.connect('C:\\Users\\jaspe\\Documents\\Codes\\ktv-extractor\\ktv.sqlite3', autocommit=True) as conn:
        conn.row_factory = sqlite3.Row
        
        with closing(conn.cursor()) as cursor:
            cursor.execute('SELECT * FROM song WHERE audio_only = false')
            rows = cursor.fetchall()
            tasks = []
            for row in rows:
                tasks.append(asyncio.create_task(process_and_update(conn, row['path'], row['id'])))
        await asyncio.gather(*tasks)
        print('cursor closed')

    print('conn closed')

asyncio.run(main())