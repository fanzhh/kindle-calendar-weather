#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""天气数据：Open-Meteo（免费、无需 API Key）+ 本地缓存兜底。

只依赖标准库，避免在 Mac mini 上多装东西。取数失败时回落到上一次
成功的缓存，保证面板永远有内容可画。
"""

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

API = "https://api.open-meteo.com/v1/forecast"

# 济宁（山东省）
# 改成你的城市：name 是显示名，经纬度用小数点十进制度数
PLACE = {"name": "北京", "latitude": 39.9042, "longitude": 116.4074, "timezone": "Asia/Shanghai"}

# WMO weather code -> (中文描述, 图标类型)
# 图标类型：sun / partly / cloud / fog / drizzle / rain / shower / snow / thunder
_WMO = {
    0: ("晴", "sun"),
    1: ("少云", "partly"),
    2: ("多云", "partly"),
    3: ("阴", "cloud"),
    45: ("雾", "fog"),
    48: ("雾凇", "fog"),
    51: ("小毛毛雨", "drizzle"),
    53: ("毛毛雨", "drizzle"),
    55: ("大毛毛雨", "drizzle"),
    56: ("冻毛毛雨", "drizzle"),
    57: ("冻毛毛雨", "drizzle"),
    61: ("小雨", "rain"),
    63: ("中雨", "rain"),
    65: ("大雨", "rain"),
    66: ("冻雨", "rain"),
    67: ("冻雨", "rain"),
    71: ("小雪", "snow"),
    73: ("中雪", "snow"),
    75: ("大雪", "snow"),
    77: ("雪粒", "snow"),
    80: ("阵雨", "shower"),
    81: ("阵雨", "shower"),
    82: ("强阵雨", "shower"),
    85: ("阵雪", "snow"),
    86: ("强阵雪", "snow"),
    95: ("雷阵雨", "thunder"),
    96: ("雷阵雨伴冰雹", "thunder"),
    99: ("强雷暴伴冰雹", "thunder"),
}


def describe(code: int):
    """WMO 天气码 -> (中文描述, 图标类型)。"""
    return _WMO.get(int(code), ("未知", "cloud"))


@dataclass
class Day:
    date: date
    code: int
    tmax: float
    tmin: float
    pop: Optional[int] = None      # 降水概率 %

    @property
    def desc(self) -> str:
        return describe(self.code)[0]

    @property
    def icon(self) -> str:
        return describe(self.code)[1]

    @property
    def week(self) -> str:
        from .lunar import week_name
        return week_name(self.date)


@dataclass
class Weather:
    place: str
    fetched_at: datetime
    temp: float
    feels: float
    humidity: int
    wind: float
    code: int
    days: List[Day] = field(default_factory=list)
    stale: bool = False            # True 表示来自缓存（网络失败）

    @property
    def desc(self) -> str:
        return describe(self.code)[0]

    @property
    def icon(self) -> str:
        return describe(self.code)[1]


def _cache_path() -> str:
    """缓存路径：默认 <项目>/cache/weather.json，可用 KINDLE_DASH_CACHE 覆盖。"""
    base = os.environ.get("KINDLE_DASH_CACHE") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "weather.json")


CURRENT_VARS = ("temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,wind_speed_10m")
DAILY_VARS = "weather_code,temperature_2m_max,temperature_2m_min"
POP_VAR = "precipitation_probability_max"

# 主模型：中国气象局 GRAPES（和中国手机天气 App 同源，湿度/温度更接近）
# 需要别的模型可改成 best_match / icon_seamless / gfs_seamless 等
PRIMARY_MODEL = os.environ.get("KINDLE_DASH_MODEL", "cma_grapes_global")


def _get_json(query: str, timeout: float) -> dict:
    req = urllib.request.Request(
        API + query,
        headers={"User-Agent": "kindle-dash/1.0 (+mac-mini renderer)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _base_query(place: dict, daily_vars: str, model: str = "") -> str:
    query = (
        f"?latitude={place['latitude']}&longitude={place['longitude']}"
        f"&current={CURRENT_VARS}"
        f"&daily={daily_vars}"
        f"&timezone={place['timezone'].replace('/', '%2F')}&forecast_days=4"
    )
    if model:
        query += f"&models={model}"
    return query


def _fetch(place: dict, timeout: float) -> dict:
    """取天气。

    主数据用中国气象局 GRAPES 模型（和中国手机天气 App 同源），
    但它不提供降水概率，所以再向默认模型补一次。
    主模型失败时整体回落到默认模型。
    """
    try:
        payload = _get_json(_base_query(place, DAILY_VARS, PRIMARY_MODEL), timeout)
        if payload.get("current", {}).get("temperature_2m") is None:
            raise ValueError("主模型无数据")
    except Exception:
        payload = _get_json(_base_query(place, DAILY_VARS), timeout)
        payload["_fallback_model"] = True
        return payload

    # 补降水概率（CMA 不提供，返回 None）
    try:
        extra = _get_json(_base_query(place, POP_VAR), timeout)
        payload["daily"][POP_VAR] = extra["daily"][POP_VAR]
    except Exception:
        payload["daily"][POP_VAR] = [None] * len(payload["daily"]["time"])
    return payload


def _parse(payload: dict, place: dict) -> Weather:
    cur = payload["current"]
    daily = payload["daily"]
    days = []
    for i, iso in enumerate(daily["time"]):
        days.append(Day(
            date=date.fromisoformat(iso),
            code=int(daily["weather_code"][i]),
            tmax=float(daily["temperature_2m_max"][i]),
            tmin=float(daily["temperature_2m_min"][i]),
            pop=(int(daily["precipitation_probability_max"][i])
                 if daily.get("precipitation_probability_max", [None])[i] is not None else None),
        ))
    return Weather(
        place=place["name"],
        fetched_at=datetime.now(),
        temp=float(cur["temperature_2m"]),
        feels=float(cur["apparent_temperature"]),
        humidity=int(cur["relative_humidity_2m"]),
        wind=float(cur["wind_speed_10m"]),
        code=int(cur["weather_code"]),
        days=days,
    )


def get_weather(place: dict = PLACE, timeout: float = 8.0,
                max_age: float = 600.0) -> Weather:
    """取天气。优先用未过期的缓存，其次联网，最后回落到过期缓存。"""
    cache = _cache_path()
    if os.path.exists(cache):
        age = time.time() - os.path.getmtime(cache)
        if age < max_age:
            try:
                with open(cache, encoding="utf-8") as fh:
                    return _from_json(json.load(fh), stale=False)
            except Exception:
                pass
    try:
        payload = _fetch(place, timeout)
        with open(cache, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        return _parse(payload, place)
    except Exception:
        if os.path.exists(cache):
            with open(cache, encoding="utf-8") as fh:
                return _from_json(json.load(fh), stale=True)
        raise


def _from_json(payload: dict, stale: bool) -> Weather:
    cur = payload["current"]
    daily = payload["daily"]
    days = []
    for i, iso in enumerate(daily["time"]):
        pop_list = daily.get("precipitation_probability_max") or []
        pop = pop_list[i] if i < len(pop_list) and pop_list[i] is not None else None
        days.append(Day(
            date=date.fromisoformat(iso),
            code=int(daily["weather_code"][i]),
            tmax=float(daily["temperature_2m_max"][i]),
            tmin=float(daily["temperature_2m_min"][i]),
            pop=int(pop) if pop is not None else None,
        ))
    return Weather(
        place=JINING["name"],
        fetched_at=datetime.fromtimestamp(os.path.getmtime(_cache_path())),
        temp=float(cur["temperature_2m"]),
        feels=float(cur["apparent_temperature"]),
        humidity=int(cur["relative_humidity_2m"]),
        wind=float(cur["wind_speed_10m"]),
        code=int(cur["weather_code"]),
        days=days,
        stale=stale,
    )


if __name__ == "__main__":
    w = get_weather(max_age=0)
    print(f"{w.place} {w.temp:.1f}°C {w.desc} 体感{w.feels:.1f}° 湿度{w.humidity}% 风{w.wind:.1f}km/h"
          + ("  [缓存]" if w.stale else ""))
    for d in w.days:
        print(f"  {d.date} {d.week} {d.desc:<8} {d.tmin:.0f}~{d.tmax:.0f}°C"
              + (f" 降水{d.pop}%" if d.pop is not None else ""))
