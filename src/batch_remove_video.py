import sqlite3
from contextlib import closing
from ktv_extractor.process import process_tracks

from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Lock

class BoundedThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers):
        super().__init__(max_workers)
        self._work_queue = Queue(1)

lock = Lock()

def process_and_update(path: str, song_id: int):
    process_tracks(path)
    with lock:
        sql = 'UPDATE song SET audio_only = true WHERE id = %d' % (song_id)
        print(sql)
        conn.execute(sql)

with sqlite3.connect('C:\\Users\\jaspe\\Documents\\Codes\\ktv-extractor\\ktv.sqlite3', autocommit=True, check_same_thread=False) as conn:
    conn.row_factory = sqlite3.Row
    
    with closing(conn.cursor()) as cursor:
        cursor.execute('SELECT * FROM song WHERE audio_only = false')
        rows = cursor.fetchall()

        with BoundedThreadPoolExecutor(10) as pool:
            for row in rows:
                print(dict(row))
                pool.submit(process_and_update, row['path'], row['id'])
        print('pool is down')
    print('cursor closed')

print('conn closed')