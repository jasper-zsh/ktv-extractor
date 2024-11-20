from enum import Enum
from typing import Any

class LyricsType(Enum):
    PlainText = 0
    VERBATIM = 1
    LINEBYLINE = 2

class LyricsFormat(Enum):
    VERBATIMLRC = 0
    LINEBYLINELRC = 1
    ENHANCEDLRC = 2
    SRT = 3
    ASS = 4
    QRC = 5
    KRC = 6
    YRC = 7
    JSON = 8

class Source(Enum):
    MULTI = 0
    QM = 1
    KG = 2
    NE = 3
    Local = 100

    # 定义 Source 类的序列化方法
    def __json__(self, o: Any) -> str:
        if isinstance(o, Source):
            return str(o.name)
        msg = f"Object of type {o.__class__.__name__} is not JSON serializable"
        raise TypeError(msg)
