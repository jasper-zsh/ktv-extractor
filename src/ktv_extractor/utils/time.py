def time2ms(m: int | str, s: int | str, ms: int | str) -> int:
    """时间转毫秒"""
    if isinstance(ms, str) and len(ms) == 2:
        ms += "0"
    return (int(m) * 60 + int(s)) * 1000 + int(ms)