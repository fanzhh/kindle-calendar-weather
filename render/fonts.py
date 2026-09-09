#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字体探测：优先用 macOS 自带的中文字体，缺失时逐个回退。"""

import os
from functools import lru_cache

from PIL import ImageFont

# (路径, ttc 索引)；靠前的优先
_REGULAR = [
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),      # 冬青黑体简体中文 W3
    ("/System/Library/Fonts/STHeiti Light.ttc", 1),         # 华文黑体 简 Light
    ("/System/Library/Fonts/STHeiti Medium.ttc", 1),        # 华文黑体 简 Medium
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 3),   # 宋体 Light
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
]
_BOLD = [
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 2),      # 冬青黑体 W6
    ("/System/Library/Fonts/STHeiti Medium.ttc", 1),        # 华文黑体 Medium
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 1),   # 宋体 Bold
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
]


def _first_existing(cands):
    for path, index in cands:
        if os.path.exists(path):
            return path, index
    raise RuntimeError(
        "找不到可用的中文字体。请在 render/fonts.py 里补充字体路径，"
        "或安装一款中文字体（如 Noto Sans CJK）。")


@lru_cache(maxsize=None)
def _face(bold: bool):
    return _first_existing(_BOLD if bold else _REGULAR)


@lru_cache(maxsize=256)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """按字号取字体；bold=True 走较粗字面。"""
    path, index = _face(bold)
    return ImageFont.truetype(path, size, index=index)


def font_name(bold: bool = False) -> str:
    """返回实际选中的字体名，便于排查。"""
    path, index = _face(bold)
    return f"{os.path.basename(path)}#{index}"


if __name__ == "__main__":
    print("常规:", font_name(False))
    print("粗体:", font_name(True))
    f = font(24, True)
    print("样张宽度:", f.getbbox("济宁 24° 星期三")[2])
