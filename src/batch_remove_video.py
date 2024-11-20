import sqlite3
from contextlib import closing
from ktv_extractor.process import process_tracks
import asyncio
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Lock
import logging

class BoundedThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers):
        super().__init__(max_workers)
        self._work_queue = Queue(1)

sem = asyncio.Semaphore(10)

async def process_and_update(conn: sqlite3.Connection, path: str, song_id: int):
    async with sem:
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, process_tracks, path)
            sql = 'UPDATE song SET audio_only = true WHERE id = %d' % (song_id)
            print(sql)
            conn.execute(sql)
        except Exception as ex:
            logging.error(f'处理轨道失败：{path} {ex}')
            sql = 'UPDATE song SET corrupt = true WHERE id = %d' % (song_id)
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