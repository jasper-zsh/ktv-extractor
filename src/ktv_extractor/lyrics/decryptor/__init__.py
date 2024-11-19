# SPDX-FileCopyrightText: Copyright (c) 2024 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
from zlib import decompress
import logging


logger = logging.getLogger(__name__)

KRC_KEY = b"@Gaw^2tGQ61-\xce\xd2ni"


def krc_decrypt(encrypted_lyrics: bytearray | bytes) -> str:
    if isinstance(encrypted_lyrics, bytes):
        encrypted_data = bytearray(encrypted_lyrics)[4:]
    elif isinstance(encrypted_lyrics, bytearray):
        encrypted_data = encrypted_lyrics[4:]
    else:
        logger.error("无效的加密数据类型")
        msg = "无效的加密数据类型"
        raise Exception(msg)

    try:
        decrypted_data = bytearray()
        for i, item in enumerate(encrypted_data):
            decrypted_data.append(item ^ KRC_KEY[i % len(KRC_KEY)])

        return decompress(decrypted_data).decode('utf-8')
    except Exception as e:
        logger.exception("解密失败")
        msg = "解密失败"
        raise Exception(msg) from e
