from enum import Enum

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