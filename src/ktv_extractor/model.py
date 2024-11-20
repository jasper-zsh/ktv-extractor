from typing import List, Optional
from sqlalchemy import Text, Table, ForeignKey, Column
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.orm import sessionmaker

engine = None
session_factory = None

def init():
    global engine, session_factory
    engine = create_engine('sqlite:///C:\\Users\\jaspe\\Documents\\Codes\\ktv-extractor\\ktv.sqlite3', echo=False)
    session_factory = sessionmaker(engine)
    BaseModel.metadata.create_all(engine)

class BaseModel(DeclarativeBase):
    pass

song_artist_table = Table(
    'song_artist',
    BaseModel.metadata,
    Column('song_id', ForeignKey('song.id')),
    Column('artist_id', ForeignKey('artist.id'))
)

song_tag_table = Table(
    'song_tag',
    BaseModel.metadata,
    Column('song_id', ForeignKey('song.id')),
    Column('tag_id', ForeignKey('tag.id'))
)

class Song(BaseModel):
    __tablename__ = 'song'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text(collation='NOCASE'), index=True)
    pinyin_head: Mapped[str] = mapped_column(Text(collation='NOCASE'), index=True)
    path: Mapped[str] = mapped_column(Text(collation='NOCASE'), index=True)
    lrc_path: Mapped[Optional[str]] = mapped_column(Text())
    lrc_fails: Mapped[int] = mapped_column()
    audio_only: Mapped[bool] = mapped_column()

    artists: Mapped[List['Artist']] = relationship(secondary=song_artist_table)
    tags: Mapped[List['Tag']] = relationship(secondary=song_tag_table)

class Artist(BaseModel):
    __tablename__ = 'artist'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text(collation='NOCASE'), index=True)
    pinyin_head: Mapped[str] = mapped_column(Text(collation='NOCASE'), index=True)

class Tag(BaseModel):
    __tablename__ = 'tag'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text(collation='NOCASE'), index=True)