def time2ms(m: int | str, s: int | str, ms: int | str) -> int:
    """时间转毫秒"""
    if isinstance(ms, str) and len(ms) == 2:
        ms += "0"
    return (int(m) * 60 + int(s)) * 1000 + int(ms)

def get_divmod_time(ms: int) -> tuple[int, int, int, int]:
    total_s, ms = divmod(ms, 1000)
    h, remainder = divmod(total_s, 3600)
    return h, *divmod(remainder, 60), ms

def ms2formattime(ms: int) -> str:
    _h, m, s, ms = get_divmod_time(ms)
    return f"{int(m):02d}:{int(s):02d}.{int(ms):03d}"
