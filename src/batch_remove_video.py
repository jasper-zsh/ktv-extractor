import sqlite3
from ktv_extractor import model
from ktv_extractor.process import process_tracks

from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Lock

class BoundedThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers):
        super().__init__(max_workers)
        self._work_queue = Queue(1)

with sqlite3.connect('C:\\Users\\jaspe\\Documents\\Codes\\ktv-extractor\\ktv.sqlite3', autocommit=True, check_same_thread=False) as conn:
    conn.row_factory = sqlite3.Row
    lock = Lock()

    cursor = conn.execute('SELECT * FROM song WHERE audio_only = false')
    rows = cursor.fetchall()

    with BoundedThreadPoolExecutor(10) as pool:
        for row in rows:
            print(dict(row))
            song_id = row['id']
            f = pool.submit(process_tracks, row['path'])
            def update(*args):
                with lock:
                    sql = 'UPDATE song SET audio_only = true WHERE id = %d' % (song_id)
                    print(sql)
                    conn.execute(sql)
            f.add_done_callback(update)
        pool.shutdown()
    cursor.close()