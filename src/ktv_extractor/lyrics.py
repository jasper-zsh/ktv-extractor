import threading
import socket
import json

def fetch_lyrics(info):
    with socket.create_connection(('127.0.0.1', 36295)) as conn:
        req = {
            'task': 'fetch_lyrics',
            'song_info': info,
        }
        payload_bytes = json.dumps(req).encode('utf-8')
        length_bytes = len(payload_bytes).to_bytes(4, byteorder='big')
        conn.send(length_bytes+payload_bytes)
        raw_recv_length = conn.recv(4)
        recv_length = int.from_bytes(raw_recv_length, byteorder='big')
        raw_response = conn.recv(recv_length)
        response = json.loads(raw_response)
        return response.get('lyrics')