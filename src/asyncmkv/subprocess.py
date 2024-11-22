import asyncio
import subprocess as sp

async def check_output(*args):
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode:
        raise sp.CalledProcessError(proc.returncode, args, stdout, stderr)
    return stdout

async def run(*args, stdout = asyncio.subprocess.PIPE, stderr = asyncio.subprocess.PIPE, check: bool = False):
    proc = await asyncio.create_subprocess_exec(*args, stdout=stdout, stderr=stderr)
    out, err = await proc.communicate()
    if check and proc.returncode:
        raise sp.CalledProcessError(proc.returncode, args, out, err)
    return out