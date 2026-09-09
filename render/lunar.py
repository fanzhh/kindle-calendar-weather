#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""农历 / 节气 / 节日换算（纯标准库，覆盖 1900-2100）。

用于 Kindle 日历面板：把公历日期换成农历日、节气和传统节日。

算法：1900-2100 农历年信息表（每年 20 bit）
    bit16     : 闰月是 30 天(1) 还是 29 天(0)
    bit15..4  : 十二个月的大小（1=30 天，0=29 天），从正月到腊月
    bit3..0   : 闰月月份（0=当年无闰月）
农历 1900 年正月初一 == 公历 1900-01-31。

节气用经典近似公式（1900 为基准的分钟偏移表），在 1900-2100 范围内
误差极小，用于日历标注足够。
"""

from datetime import date, datetime, timedelta

_BASE_YEAR = 1900
_MAX_YEAR = 2100
_BASE_DATE = date(1900, 1, 31)

_LUNAR_INFO = [
    0x04bd8, 0x04ae0, 0x0a570, 0x054d5, 0x0d260, 0x0d950, 0x16554, 0x056a0, 0x09ad0, 0x055d2,  # 1900-1909
    0x04ae0, 0x0a5b6, 0x0a4d0, 0x0d250, 0x1d255, 0x0b540, 0x0d6a0, 0x0ada2, 0x095b0, 0x14977,  # 1910-1919
    0x04970, 0x0a4b0, 0x0b4b5, 0x06a50, 0x06d40, 0x1ab54, 0x02b60, 0x09570, 0x052f2, 0x04970,  # 1920-1929
    0x06566, 0x0d4a0, 0x0ea50, 0x06e95, 0x05ad0, 0x02b60, 0x186e3, 0x092e0, 0x1c8d7, 0x0c950,  # 1930-1939
    0x0d4a0, 0x1d8a6, 0x0b550, 0x056a0, 0x1a5b4, 0x025d0, 0x092d0, 0x0d2b2, 0x0a950, 0x0b557,  # 1940-1949
    0x06ca0, 0x0b550, 0x15355, 0x04da0, 0x0a5b0, 0x14573, 0x052b0, 0x0a9a8, 0x0e950, 0x06aa0,  # 1950-1959
    0x0aea6, 0x0ab50, 0x04b60, 0x0aae4, 0x0a570, 0x05260, 0x0f263, 0x0d950, 0x05b57, 0x056a0,  # 1960-1969
    0x096d0, 0x04dd5, 0x04ad0, 0x0a4d0, 0x0d4d4, 0x0d250, 0x0d558, 0x0b540, 0x0b6a0, 0x195a6,  # 1970-1979
    0x095b0, 0x049b0, 0x0a974, 0x0a4b0, 0x0b27a, 0x06a50, 0x06d40, 0x0af46, 0x0ab60, 0x09570,  # 1980-1989
    0x04af5, 0x04970, 0x064b0, 0x074a3, 0x0ea50, 0x06b58, 0x055c0, 0x0ab60, 0x096d5, 0x092e0,  # 1990-1999
    0x0c960, 0x0d954, 0x0d4a0, 0x0da50, 0x07552, 0x056a0, 0x0abb7, 0x025d0, 0x092d0, 0x0cab5,  # 2000-2009
    0x0a950, 0x0b4a0, 0x0baa4, 0x0ad50, 0x055d9, 0x04ba0, 0x0a5b0, 0x15176, 0x052b0, 0x0a930,  # 2010-2019
    0x07954, 0x06aa0, 0x0ad50, 0x05b52, 0x04b60, 0x0a6e6, 0x0a4e0, 0x0d260, 0x0ea65, 0x0d530,  # 2020-2029
    0x05aa0, 0x076a3, 0x096d0, 0x04afb, 0x04ad0, 0x0a4d0, 0x1d0b6, 0x0d250, 0x0d520, 0x0dd45,  # 2030-2039
    0x0b5a0, 0x056d0, 0x055b2, 0x049b0, 0x0a577, 0x0a4b0, 0x0aa50, 0x1b255, 0x06d20, 0x0ada0,  # 2040-2049
    0x14b63, 0x09370, 0x049f8, 0x04970, 0x064b0, 0x168a6, 0x0ea50, 0x06b20, 0x1a6c4, 0x0aae0,  # 2050-2059
    0x0a2e0, 0x0d2e3, 0x0c960, 0x0d557, 0x0d4a0, 0x0da50, 0x05d55, 0x056a0, 0x0a6d0, 0x055d4,  # 2060-2069
    0x052d0, 0x0a9b8, 0x0a950, 0x0b4a0, 0x0b6a6, 0x0ad50, 0x055a0, 0x0aba4, 0x0a5b0, 0x052b0,  # 2070-2079
    0x0b273, 0x06930, 0x07337, 0x06aa0, 0x0ad50, 0x14b55, 0x04b60, 0x0a570, 0x054e4, 0x0d160,  # 2080-2089
    0x0e968, 0x0d520, 0x0daa0, 0x16aa6, 0x056d0, 0x04ae0, 0x0a9d4, 0x0a2d0, 0x0d150, 0x0f252,  # 2090-2099
    0x0d520,  # 2100
]

_MONTH_CN = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊"]
_DAY_CN = ["初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
           "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
           "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十"]
_WEEK_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
_GAN = "甲乙丙丁戊己庚辛壬癸"
_ZHI = "子丑寅卯辰巳午未申酉戌亥"

# 节气：经典近似公式（基准 1900-01-06 02:05，单位分钟）
_S_TERM_MINUTES = [0, 21208, 42467, 63836, 85337, 107014, 128867, 150921, 173149,
                   195551, 218072, 240693, 263343, 285989, 308563, 331033, 353350,
                   375494, 397447, 419210, 440795, 462224, 483532, 504758]
_S_TERM_NAMES = ["小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
                 "立夏", "小满", "芒种", "夏至", "小暑", "大暑", "立秋", "处暑",
                 "白露", "秋分", "寒露", "霜降", "立冬", "小雪", "大雪", "冬至"]
_S_TERM_BASE = datetime(1900, 1, 6, 2, 5)

# 农历节日：名称 -> (月, 日)
_LUNAR_FESTIVALS = {
    (1, 1): "春节", (1, 15): "元宵", (2, 2): "龙抬头", (5, 5): "端午",
    (7, 7): "七夕", (7, 15): "中元", (8, 15): "中秋", (9, 9): "重阳",
    (12, 8): "腊八", (12, 23): "小年",
}
# 公历节日：月 -> {日: 名称}
_SOLAR_FESTIVALS = {
    1: {1: "元旦"}, 3: {8: "妇女节", 12: "植树节"}, 5: {1: "劳动节", 4: "青年节"},
    6: {1: "儿童节"}, 7: {1: "建党节"}, 8: {1: "建军节"}, 9: {10: "教师节"},
    10: {1: "国庆节"}, 12: {25: "圣诞节"},
}


def _info(year: int) -> int:
    if not _BASE_YEAR <= year <= _MAX_YEAR:
        raise ValueError(f"年份 {year} 超出支持范围 {_BASE_YEAR}-{_MAX_YEAR}")
    return _LUNAR_INFO[year - _BASE_YEAR]


def leap_month(year: int) -> int:
    """农历 year 年的闰月月份（1-12），无闰月返回 0。"""
    return _info(year) & 0xF


def leap_days(year: int) -> int:
    """闰月天数，无闰月返回 0。"""
    if leap_month(year):
        return 30 if _info(year) & 0x10000 else 29
    return 0


def month_days(year: int, month: int) -> int:
    """农历 year 年第 month 个普通月的天数。"""
    return 30 if _info(year) & (0x10000 >> month) else 29


def year_days(year: int) -> int:
    """农历 year 年总天数。"""
    return sum(month_days(year, m) for m in range(1, 13)) + leap_days(year)


def _months_of(year: int):
    """按时间顺序返回 (月份, 是否闰月, 天数)。"""
    leap = leap_month(year)
    seq = []
    for m in range(1, 13):
        seq.append((m, False, month_days(year, m)))
        if m == leap:
            seq.append((m, True, leap_days(year)))
    return seq


def lunar_to_solar(year: int, month: int, day: int, is_leap: bool = False) -> date:
    """农历 -> 公历。"""
    offset = 0
    for y in range(_BASE_YEAR, year):
        offset += year_days(y)
    for m, lp, dm in _months_of(year):
        if m == month and lp == is_leap:
            if not 1 <= day <= dm:
                raise ValueError(f"{year} 年{'闰' if lp else ''}{m}月只有 {dm} 天")
            return _BASE_DATE + timedelta(days=offset + day - 1)
        offset += dm
    raise ValueError(f"{year} 年没有闰{month}月")


def solar_to_lunar(d: date):
    """公历 -> (农历年, 月, 日, 是否闰月)。"""
    if d < _BASE_DATE or d > date(_MAX_YEAR, 12, 31):
        raise ValueError(f"日期 {d} 超出支持范围")
    offset = (d - _BASE_DATE).days
    year = _BASE_YEAR
    while year <= _MAX_YEAR:
        yd = year_days(year)
        if offset < yd:
            break
        offset -= yd
        year += 1
    for m, lp, dm in _months_of(year):
        if offset < dm:
            return (year, m, offset + 1, lp)
        offset -= dm
    raise ValueError("农历换算失败")


def solar_term(d: date) -> str:
    """若 d 是节气当天，返回节气名，否则返回空字符串。"""
    for n in range(24):
        minutes = 525948.76 * (d.year - 1900) + _S_TERM_MINUTES[n]
        if (_S_TERM_BASE + timedelta(minutes=minutes)).date() == d:
            return _S_TERM_NAMES[n]
    return ""


def lunar_month_name(month: int, is_leap: bool = False) -> str:
    """农历月份中文名。"""
    return ("闰" if is_leap else "") + _MONTH_CN[month - 1] + "月"


def lunar_day_name(day: int) -> str:
    """农历日中文名。"""
    return _DAY_CN[day - 1]


def week_name(d: date) -> str:
    """中文星期。"""
    return _WEEK_CN[d.weekday()]


def ganzhi_year(lunar_year: int) -> str:
    """农历年的干支，例如 2026 -> 丙午。"""
    return _GAN[(lunar_year - 4) % 10] + _ZHI[(lunar_year - 4) % 12]


def cell_label(d: date) -> tuple:
    """日历格子里的第二行文字。

    返回 (文字, 是否节日)。优先级：节日 > 节气 > 农历初一显示月名 > 农历日。
    """
    lunar_year, month, day, is_leap = solar_to_lunar(d)
    # 除夕：腊月最后一天（次年春节前一天）
    if (d + timedelta(days=1)) == lunar_to_solar(d.year + 1, 1, 1):
        return ("除夕", True)
    festival = _LUNAR_FESTIVALS.get((month, day)) if not is_leap else None
    if festival:
        return (festival, True)
    solar_festival = _SOLAR_FESTIVALS.get(d.month, {}).get(d.day)
    if solar_festival:
        return (solar_festival, True)
    term = solar_term(d)
    if term:
        return (term, True)
    if day == 1:
        return (lunar_month_name(month, is_leap), False)
    return (lunar_day_name(day), False)


def day_summary(d: date) -> dict:
    """一天的完整中文信息，供面板头部使用。"""
    lunar_year, month, day, is_leap = solar_to_lunar(d)
    term = solar_term(d)
    label, is_festival = cell_label(d)
    return {
        "date": d,
        "week": week_name(d),
        "lunar_year": lunar_year,
        "lunar_month": month,
        "lunar_day": day,
        "is_leap_month": is_leap,
        "lunar_text": f"{lunar_month_name(month, is_leap)}{lunar_day_name(day)}",
        "ganzhi": ganzhi_year(lunar_year),
        "solar_term": term,
        "festival": label if is_festival else "",
        "label": label,
    }


if __name__ == "__main__":
    # 自测锚点
    cases = [
        (lunar_to_solar(2025, 1, 1), date(2025, 1, 29), "2025 春节"),
        (lunar_to_solar(2024, 1, 1), date(2024, 2, 10), "2024 春节"),
        (lunar_to_solar(2026, 1, 1), date(2026, 2, 17), "2026 春节"),
        (lunar_to_solar(2025, 8, 15), date(2025, 10, 6), "2025 中秋"),
        (lunar_to_solar(2026, 8, 15), date(2026, 9, 25), "2026 中秋"),
        (lunar_to_solar(2023, 2, 1, True), date(2023, 3, 22), "2023 闰二月初一"),
    ]
    ok = True
    for got, want, name in cases:
        flag = "OK" if got == want else "FAIL"
        ok = ok and got == want
        print(f"[{flag}] {name}: {got} (期望 {want})")
    print("今天:", day_summary(date.today()))
    raise SystemExit(0 if ok else 1)
