#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「当月月历 + 农历/节气/节日 + 天气」渲染成 600×800 的 8 位灰度 PNG。

目标设备：Kindle 7（KT2，600×800，167 ppi，16 级灰阶，无前置灯）。
输出直接喂给 linkss 屏保目录 / eips -g / KOReader 屏保。

用法：
    python3 -m render.dash -o preview/dash-preview.png
    python3 -m render.dash -o /tmp/x.png --date 2026-09-25
"""

import argparse
import os
from datetime import date, datetime, timedelta

from PIL import Image, ImageDraw

from . import fonts, lunar
from .weather import JINING, Weather, get_weather

W, H = 600, 800
MARGIN = 14
BLACK, DARK, MID, LIGHT, LINE, WHITE = 0, 60, 110, 165, 200, 255

# 纵向分区
HEADER_H = 94
WEEKDAY_Y = 98
GRID_Y = 126
GRID_ROW_H = 53
GRID_COLS = 7
CELL_W = 82
GRID_X = 13
WEATHER_Y = GRID_Y + GRID_ROW_H * 6 + 4          # 448
FORECAST_Y = WEATHER_Y + 142                      # 590
FORECAST_ROW_H = 60
FOOTER_Y = FORECAST_Y + FORECAST_ROW_H * 3 + 2    # 772


# --------------------------------------------------------------------------
# 天气图标（纯矢量，无外部素材）
# --------------------------------------------------------------------------
def _sun(d, x, y, s, fill=BLACK):
    r = s * 0.26
    cx, cy = x + s / 2, y + s / 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    for i in range(8):
        import math
        a = math.radians(i * 45)
        x0, y0 = cx + math.cos(a) * r * 1.45, cy + math.sin(a) * r * 1.45
        x1, y1 = cx + math.cos(a) * r * 1.95, cy + math.sin(a) * r * 1.95
        d.line([x0, y0, x1, y1], fill=fill, width=max(1, int(s * 0.045)))


def _cloud(d, x, y, s, fill=BLACK):
    w = s * 0.86
    h = s * 0.40
    bx, by = x + (s - w) / 2, y + s * 0.34
    d.ellipse([bx, by - h * 0.55, bx + w * 0.52, by + h * 0.55], fill=fill)
    d.ellipse([bx + w * 0.24, by - h * 1.05, bx + w * 0.92, by + h * 0.55], fill=fill)
    d.ellipse([bx + w * 0.10, by - h * 0.30, bx + w, by + h * 0.62], fill=fill)
    d.rectangle([bx + w * 0.12, by - h * 0.05, bx + w * 0.88, by + h * 0.55], fill=fill)


def _drops(d, x, y, s, count=3, dash=False):
    for i in range(count):
        dx = x + s * (0.26 + i * 0.20)
        y0 = y + s * 0.74
        if dash:
            d.line([dx, y0, dx - s * 0.05, y0 + s * 0.10], fill=BLACK, width=max(1, int(s * 0.05)))
        else:
            d.ellipse([dx - s * 0.03, y0, dx + s * 0.03, y0 + s * 0.12], fill=BLACK)


def _flakes(d, x, y, s, count=3):
    for i in range(count):
        cx = x + s * (0.26 + i * 0.20)
        cy = y + s * 0.80
        r = s * 0.045
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BLACK)
        d.line([cx - r * 1.6, cy, cx + r * 1.6, cy], fill=BLACK, width=1)


def _bolt(d, x, y, s):
    pts = [(x + s * 0.48, y + s * 0.66), (x + s * 0.40, y + s * 0.86),
           (x + s * 0.50, y + s * 0.86), (x + s * 0.42, y + s * 1.0),
           (x + s * 0.62, y + s * 0.80), (x + s * 0.52, y + s * 0.80),
           (x + s * 0.58, y + s * 0.66)]
    d.polygon(pts, fill=BLACK)


def draw_icon(d, x, y, s, kind):
    """在 (x, y) 处画边长 s 的天气图标。"""
    if kind == "sun":
        _sun(d, x, y, s)
    elif kind == "partly":
        _sun(d, x + s * 0.30, y - s * 0.06, s * 0.62)
        _cloud(d, x, y + s * 0.12, s)
    elif kind == "cloud":
        _cloud(d, x, y, s)
    elif kind == "fog":
        for i in range(3):
            yy = y + s * (0.36 + i * 0.22)
            d.line([x + s * 0.08, yy, x + s * 0.92 - i * s * 0.10, yy],
                   fill=BLACK, width=max(1, int(s * 0.055)))
    elif kind == "drizzle":
        _cloud(d, x, y, s)
        _drops(d, x, y, s, dash=True)
    elif kind in ("rain", "shower"):
        _cloud(d, x, y, s)
        _drops(d, x, y, s)
    elif kind == "snow":
        _cloud(d, x, y, s)
        _flakes(d, x, y, s)
    elif kind == "thunder":
        _cloud(d, x, y, s)
        _bolt(d, x, y, s)
    else:
        _cloud(d, x, y, s)


# --------------------------------------------------------------------------
# 主渲染
# --------------------------------------------------------------------------
def _line(d, y, x0=MARGIN, x1=W - MARGIN, fill=LINE):
    d.line([x0, y, x1, y], fill=fill, width=1)


def _header(d, today: date, place: str):
    info = lunar.day_summary(today)
    d.text((MARGIN, 8), place, font=fonts.font(34, True), fill=BLACK, anchor="lt")

    sub = info["lunar_text"]
    if info["solar_term"]:
        sub += f" · {info['solar_term']}"
    if info["festival"] and info["festival"] != info["solar_term"]:
        sub = f"{info['festival']} · {sub}"
    d.text((MARGIN, 56), sub, font=fonts.font(16), fill=DARK, anchor="lt")

    d.text((W - MARGIN, 10), f"{today.year}年{today.month}月{today.day}日",
           font=fonts.font(22, True), fill=BLACK, anchor="rt")
    d.text((W - MARGIN, 46), info["week"], font=fonts.font(18), fill=DARK, anchor="rt")
    d.text((W - MARGIN, 70), f"{info['ganzhi']}年",
           font=fonts.font(14), fill=MID, anchor="rt")
    _line(d, HEADER_H)


def _weekday_row(d):
    for i, name in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
        cx = GRID_X + i * CELL_W + CELL_W / 2
        d.text((cx, WEEKDAY_Y), name, font=fonts.font(17, True),
               fill=BLACK if i < 5 else DARK, anchor="mt")
    _line(d, GRID_Y - 2)


def _calendar(d, today: date):
    first = date(today.year, today.month, 1)
    grid_start = first - timedelta(days=first.weekday())   # 周一开头
    f_day = fonts.font(24, True)
    f_label = fonts.font(14)
    for i in range(42):
        cell = grid_start + timedelta(days=i)
        col, row = i % 7, i // 7
        x0 = GRID_X + col * CELL_W
        y0 = GRID_Y + row * GRID_ROW_H
        in_month = (cell.month == today.month and cell.year == today.year)
        is_today = (cell == today)

        if is_today:
            d.rectangle([x0 + 1, y0 + 1, x0 + CELL_W - 2, y0 + GRID_ROW_H - 3], fill=BLACK)
            num_fill = label_fill = WHITE
        else:
            num_fill = BLACK if in_month else LIGHT
            label_fill = DARK if in_month else LIGHT

        d.text((x0 + 7, y0 + 4), str(cell.day), font=f_day, fill=num_fill, anchor="lt")

        if in_month:
            text, is_fest = lunar.cell_label(cell)
            d.text((x0 + 7, y0 + 32), text, font=f_label,
                   fill=(num_fill if is_fest or is_today else label_fill), anchor="lt")
    _line(d, WEATHER_Y - 4)


def _today_weather(d, w: Weather, today: date):
    x, y = MARGIN, WEATHER_Y
    draw_icon(d, x, y + 6, 76, w.icon)
    d.text((x + 92, y - 4), f"{w.temp:.0f}°", font=fonts.font(62, True),
           fill=BLACK, anchor="lt")
    d.text((x + 96, y + 74), w.desc, font=fonts.font(22), fill=BLACK, anchor="lt")

    today_fc = next((dd for dd in w.days if dd.date == today), w.days[0] if w.days else None)
    if today_fc:
        d.text((W - MARGIN, y + 2), f"今天 {today_fc.tmin:.0f}~{today_fc.tmax:.0f}°",
               font=fonts.font(20, True), fill=BLACK, anchor="rt")
        if today_fc.pop is not None:
            d.text((W - MARGIN, y + 30), f"降水概率 {today_fc.pop}%",
                   font=fonts.font(15), fill=DARK, anchor="rt")

    detail = f"体感 {w.feels:.0f}°  ·  湿度 {w.humidity}%  ·  风 {w.wind:.0f} km/h"
    d.text((x, y + 102), detail, font=fonts.font(15), fill=DARK, anchor="lt")


def _forecast(d, w: Weather, today: date):
    d.text((MARGIN, FORECAST_Y - 22), "未来天气", font=fonts.font(15, True),
           fill=BLACK, anchor="lt")
    rows = [dd for dd in w.days if dd.date > today][:3]
    f_day = fonts.font(18)
    f_temp = fonts.font(23, True)
    f_pop = fonts.font(15)
    for i, dd in enumerate(rows):
        y0 = FORECAST_Y + i * FORECAST_ROW_H
        d.text((MARGIN, y0 + 16), f"{dd.date.month}/{dd.date.day} {dd.week}",
               font=f_day, fill=DARK, anchor="lt")
        draw_icon(d, 168, y0 + 8, 42, dd.icon)
        d.text((222, y0 + 14), f"{dd.tmin:.0f}~{dd.tmax:.0f}°",
               font=f_temp, fill=BLACK, anchor="lt")
        d.text((340, y0 + 18), dd.desc, font=f_day, fill=DARK, anchor="lt")
        if dd.pop is not None:
            d.text((W - MARGIN, y0 + 18), f"降水 {dd.pop}%", font=f_pop,
                   fill=MID, anchor="rt")
        if i < len(rows) - 1:
            _line(d, y0 + FORECAST_ROW_H - 8, fill=LINE)


def _footer(d, w: Weather):
    _line(d, FOOTER_Y, fill=LIGHT)
    stamp = w.fetched_at.strftime("%m-%d %H:%M")
    note = "更新 " + stamp
    if w.stale:
        note += "（缓存）"
    d.text((MARGIN, FOOTER_Y + 8), note, font=fonts.font(13), fill=DARK, anchor="lt")
    d.text((W - MARGIN, FOOTER_Y + 8), "Open-Meteo · 济宁",
           font=fonts.font(13), fill=DARK, anchor="rt")


def render(w: Weather, today: date = None, size=(W, H), banner: str = "") -> Image.Image:
    """渲染成 8 位灰度图。banner 非空时在中部画一条黑底白字横幅（用于验证）。"""
    today = today or date.today()
    img = Image.new("L", size, WHITE)
    d = ImageDraw.Draw(img)
    _header(d, today, w.place)
    _weekday_row(d)
    _calendar(d, today)
    _today_weather(d, w, today)
    _forecast(d, w, today)
    _footer(d, w)
    if banner:
        _banner(d, banner)
    return img


def _banner(d, text: str):
    """横跨中部的黑底白字横幅，用来肉眼确认设备是否加载了新图。"""
    y0, y1 = 330, 430
    d.rectangle([0, y0, W, y1], fill=BLACK)
    f = fonts.font(30, True)
    bbox = f.getbbox(text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((W - tw) / 2 - bbox[0], y0 + (y1 - y0 - th) / 2 - bbox[1]),
           text, font=f, fill=WHITE)


def render_today(size=(W, H)) -> Image.Image:
    """联网取数 + 渲染，供服务器调用。"""
    return render(get_weather(), size=size)


def main():
    ap = argparse.ArgumentParser(description="渲染 Kindle 日历+天气面板")
    ap.add_argument("-o", "--out", default="preview/dash-preview.png")
    ap.add_argument("--date", help="指定日期（YYYY-MM-DD），用于预览特定月份")
    ap.add_argument("--no-net", action="store_true", help="只用缓存，不联网")
    args = ap.parse_args()

    today = date.fromisoformat(args.date) if args.date else date.today()
    w = get_weather(max_age=10 ** 9 if args.no_net else 600)
    img = render(w, today=today)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    img.save(args.out, format="PNG", optimize=True)
    print(f"已写出 {args.out}  {img.size[0]}×{img.size[1]}  mode={img.mode}  "
          f"{os.path.getsize(args.out) / 1024:.1f} KB  字体={fonts.font_name(False)}")


if __name__ == "__main__":
    main()
