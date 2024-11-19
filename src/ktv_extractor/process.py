from pymkv import MKVFile
from . import model
from .model import Song, Artist, Tag
from sqlalchemy import select
from sqlalchemy.orm import scoped_session
from pathlib import Path
from pypinyin import pinyin, Style
import os

def process_tracks(filepath: str):
    mkv_file = MKVFile(filepath, mkvmerge_path='C:\\Program Files\\MKVToolNix\\mkvmerge.exe')
    video_track_ids = []
    
    for track in mkv_file.tracks:
        print('found track id %s name %s codec %s default %s'%(track.track_id, track.track_name, track.track_codec, track.default_track))
        match track.track_type:
            case 'video':
                video_track_ids.append(track.track_id)
            case 'audio':
                if track.default_track:
                    print('orig.')
                else:
                    print('inst.')
    if len(video_track_ids) == 0:
        print('video track already removed')
        return
    for id in video_track_ids:
        print('remove video track %d'%(id))
        mkv_file.remove_track(id)
    mkv_file.mux(filepath+'.out')
    os.unlink(filepath)
    os.rename(filepath+'.out', filepath)

artist_seps = ['_', '^', '&', ' ']

def index(filepath: str, reindex: bool = False):
    p = Path(filepath)
    with scoped_session(model.session_factory)() as session:
        song = session.scalar(select(Song).where(Song.path == filepath))
        if song is None:
            print('indexing %s' % (filepath))
            song = Song(path=filepath, audio_only=False)
        else:
            if not reindex:
                return
            print('reindexing %d %s' % (song.id, filepath))
        
        name_parts = p.stem.split('-')
        if len(name_parts) < 2:
            song.name = name_parts[0]
        else:
            song.name = name_parts[1]
            # handle artists
            artist_names = [name_parts[0]]
            for sep in artist_seps:
                if sep in name_parts[0]:
                    artist_names = name_parts[0].strip().split(sep)
                    break
            
            artists = session.scalars(select(Artist).where(Artist.name.in_(artist_names))).all()
            song.artists = artists
            name_set = set(map(lambda x: x.name, artists))
            for name in artist_names:
                if name not in name_set:
                    artist = Artist(name=name)
                    session.add(artist)
                    song.artists.append(artist)
            for artist in song.artists:
                artist.pinyin_head = ''.join(map(lambda x: x[0], pinyin(artist.name, style=Style.FIRST_LETTER)))
            session.add_all(song.artists)
            if len(song.tags) == 0:
                # handle tags
                tag_names = list(map(lambda x: x.strip(), name_parts[2:]))
                tags = session.scalars(select(Tag).where(Tag.name.in_(tag_names))).all()
                song.tags = tags
                name_set = set(map(lambda x: x.name, tags))
                for name in tag_names:
                    if name not in name_set:
                        tag = Tag(name=name)
                        session.add(tag)
                        song.tags.append(tag)
        
        song.pinyin_head = ''.join(map(lambda x: x[0], pinyin(song.name, style=Style.FIRST_LETTER)))
        session.add(song)
        session.commit()

def process_lyrics(song: Song, filepath: str):
    print('fetching lyrics for %s' % (filepath))
    try:
        lyrics = fetch_lyrics({
            'artist': '/'.join(map(lambda x: x.name, song.artists)),
            'title': song.name,
        })
        if lyrics is not None:
            lrc_path = '.'.join(filepath.split('.')[:-1]) + '.lrc'
            with open(lrc_path, 'w', encoding='utf-8') as f:
                f.write(lyrics)
            song.lrc_path = lrc_path
    except Exception as ex:
        print('failed to fetch lyrics', ex)