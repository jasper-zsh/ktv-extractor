import re

def has_content(line: str) -> bool:
    """检查是否有实际内容"""
    content = re.sub(r"\[\d+:\d+\.\d+\]|\[\d+,\d+\]|<\d+:\d+\.\d+>", "", line).strip()
    if content in ("", "//"):
        return False
    return not (len(content) == 2 and content[0].isupper() and content[1] == "：")  # 歌手标签行
