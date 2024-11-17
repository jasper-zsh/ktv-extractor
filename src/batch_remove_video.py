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

pool = BoundedThreadPoolExecutor(10)

conn = sqlite3.connect('C:\\Users\\jaspe\\Documents\\Codes\\ktv-extractor\\ktv.sqlite3', autocommit=True, check_same_thread=False)
conn.row_factory = sqlite3.Row
lock = Lock()

cursor = conn.execute('SELECT * FROM song WHERE audio_only = false')
rows = cursor.fetchall()

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

# with scoped_session(model.session_factory)() as session:
#     songs = session.scalars(select(model.Song).where(model.Song.audio_only == False)).all()
#     for song in songs:
#         f = pool.submit(process_tracks, song.path)
#         def update(*args):
#             song.audio_only = True
#             session.commit()
#         f.add_done_callback(update)