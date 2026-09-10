#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""天气数据：气象站实况（中国天气网）+ 预报模型（Open-Meteo），本地缓存兜底。

为什么两套数据源：
  · Open-Meteo 是**数值预报模型**，网格点代表一片区域的平均值，清晨的局地低温
    会被平滑掉，与国内手机天气 App 差异可达 3℃ 以上。
  · 手机 App（中国天气网/墨迹等）显示的是**气象站实况观测**。
所以当前天气优先用实况，预报（今日高低温、未来几天）仍用模型。

只依赖标准库，避免在 Mac mini 上多装东西。取数失败时回落到上一次
成功的缓存，保证面板永远有内容可画。
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import List, Optional

API = "https://api.open-meteo.com/v1/forecast"

# 中国天气网实况（气象站观测）。城市代码见 http://www.weather.com.cn
CN_OBS = "http://d1.weather.com.cn/sk_2d/{code}.html"
CN_HEADERS = {
    "Referer": "http://www.weather.com.cn/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
}

# 济宁（山东省），城市代码 101120701
PLACE = {
    "name": "北京",
    "latitude": 39.9042,
    "longitude": 116.4074,
    "timezone": "Asia/Shanghai",
    # 中国天气网城市代码，见 http://www.weather.com.cn （北京=101010100）
    "city_code": os.environ.get("KINDLE_DASH_CITYCODE", "101010100"),
}

# 主预报模型：中国气象局 GRAPES（与国内 App 同源）
# 可换 best_match / icon_seamless / gfs_seamless 等
PRIMARY_MODEL = os.environ.get("KINDLE_DASH_MODEL", "cma_grapes_global")

# 是否使用实况观测（关掉则完全用模型）
USE_STATION = os.environ.get("KINDLE_DASH_STATION", "1") not in ("0", "false", "no")

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

# 实况的中文天气描述 -> 图标类型（按优先级匹配）
_CN_TEXT_ICON = [
    ("雷", "thunder"),
    ("冰雹", "thunder"),
    ("雪", "snow"),
    ("雨", "rain"),
    ("雾", "fog"),
    ("霾", "fog"),
    ("沙", "fog"),
    ("尘", "fog"),
    ("阴", "cloud"),
    ("云", "partly"),
    ("晴", "sun"),
]


def describe(code: int):
    """WMO 天气码 -> (中文描述, 图标类型)。"""
    return _WMO.get(int(code), ("未知", "cloud"))


def icon_from_text(text: str) -> str:
    """中文天气描述 -> 图标类型。"""
    for key, icon in _CN_TEXT_ICON:
        if key in text:
            return icon
    return "cloud"


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
    wind_text: str = ""            # 实况的风（如「1级」），为空则显示 km/h
    aqi: Optional[int] = None      # 空气质量（实况接口附带）
    desc_text: str = ""            # 实况的中文天气（如「多云」），为空则用天气码
    obs_time: str = ""             # 实况观测时间
    source: str = "model"          # station / model

    @property
    def desc(self) -> str:
        return self.desc_text or describe(self.code)[0]

    @property
    def icon(self) -> str:
        if self.desc_text:
            return icon_from_text(self.desc_text)
        return describe(self.code)[1]


# ---------------------------------------------------------------------------
# 缓存：直接缓存最终结果，避免两套数据源的时间错配
# ---------------------------------------------------------------------------
def _cache_path() -> str:
    base = os.environ.get("KINDLE_DASH_CACHE") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "weather.json")


def _to_json(w: Weather) -> dict:
    d = asdict(w)
    d["fetched_at"] = w.fetched_at.isoformat()
    for day in d["days"]:
        day["date"] = day["date"].isoformat()
    return d


def _from_json(d: dict, stale: bool) -> Weather:
    d = dict(d)
    d["fetched_at"] = datetime.fromisoformat(d["fetched_at"])
    d["days"] = [Day(date=date.fromisoformat(x["date"]), code=x["code"],
                     tmax=x["tmax"], tmin=x["tmin"], pop=x.get("pop"))
                 for x in d["days"]]
    d["stale"] = stale
    return Weather(**d)


# ---------------------------------------------------------------------------
# 数据源一：气象站实况（中国天气网）
# ---------------------------------------------------------------------------
def _fetch_station(code: str, timeout: float) -> dict:
    req = urllib.request.Request(CN_OBS.format(code=code), headers=CN_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", "replace")
    # 形如 var dataSK={...}  （有的接口带结尾分号，有的不带）
    m = re.search(r"dataSK\s*=\s*(\{.*\})", text, re.S)
    if not m:
        raise ValueError("实况接口格式变了")
    raw = json.loads(m.group(1))

    def num(key):
        v = raw.get(key)
        if v is None:
            return None
        # 接口里的值可能带单位：87% / 1km/h / 14.8℃
        s = re.sub(r"[^0-9.\-]", "", str(v))
        try:
            f = float(s)
        except (TypeError, ValueError):
            return None
        # 999 / -999 是接口的「无数据」哨兵值
        return None if abs(f) >= 999 else f

    temp = num("temp")
    if temp is None:
        raise ValueError("实况无温度数据")

    aqi = num("aqi")
    return {
        "temp": temp,
        "humidity": num("SD"),
        "wind_kmh": num("wse"),
        "wind_text": (raw.get("WS") or "").strip(),
        "wind_dir": (raw.get("WD") or "").strip(),
        "desc": (raw.get("weather") or "").strip(),
        "aqi": int(aqi) if aqi is not None else None,
        "time": (raw.get("time") or "").strip(),
    }


# ---------------------------------------------------------------------------
# 数据源二：预报模型（Open-Meteo）
# ---------------------------------------------------------------------------
CURRENT_VARS = ("temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,wind_speed_10m")
DAILY_VARS = "weather_code,temperature_2m_max,temperature_2m_min"
POP_VAR = "precipitation_probability_max"


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


def _fetch_model(place: dict, timeout: float) -> dict:
    """预报：优先 CMA GRAPES；它没有降水概率，另向默认模型补一次。"""
    try:
        payload = _get_json(_base_query(place, DAILY_VARS, PRIMARY_MODEL), timeout)
        if payload.get("current", {}).get("temperature_2m") is None:
            raise ValueError("主模型无数据")
    except Exception:
        payload = _get_json(_base_query(place, DAILY_VARS), timeout)

    try:
        extra = _get_json(_base_query(place, POP_VAR), timeout)
        payload["daily"][POP_VAR] = extra["daily"][POP_VAR]
    except Exception:
        payload["daily"][POP_VAR] = [None] * len(payload["daily"]["time"])
    return payload


def _build(place: dict, payload: dict, station: Optional[dict]) -> Weather:
    cur = payload["current"]
    daily = payload["daily"]

    days = []
    for i, iso in enumerate(daily["time"]):
        pop_list = daily.get(POP_VAR) or []
        pop = pop_list[i] if i < len(pop_list) and pop_list[i] is not None else None
        days.append(Day(
            date=date.fromisoformat(iso),
            code=int(daily["weather_code"][i]),
            tmax=float(daily["temperature_2m_max"][i]),
            tmin=float(daily["temperature_2m_min"][i]),
            pop=int(pop) if pop is not None else None,
        ))

    if station:
        # 实况是今天的真实数据点，用它把今天的高低温区间撑开，
        # 否则模型网格的平均值会把清晨的低温平滑掉（实测差 3℃ 以上）
        if days and days[0].date == date.today():
            days[0].tmin = min(days[0].tmin, station["temp"])
            days[0].tmax = max(days[0].tmax, station["temp"])

        return Weather(
            place=place["name"],
            fetched_at=datetime.now(),
            temp=station["temp"],
            feels=station["temp"],          # 实况没有体感，稍后用模型值补
            humidity=int(station["humidity"]) if station["humidity"] is not None else 0,
            wind=station["wind_kmh"] or 0.0,
            code=int(cur["weather_code"]),
            days=days,
            wind_text=station["wind_text"],
            aqi=station["aqi"],
            desc_text=station["desc"],
            obs_time=station["time"],
            source="station",
        )

    return Weather(
        place=place["name"],
        fetched_at=datetime.now(),
        temp=float(cur["temperature_2m"]),
        feels=float(cur["apparent_temperature"]),
        humidity=int(cur["relative_humidity_2m"]),
        wind=float(cur["wind_speed_10m"]),
        code=int(cur["weather_code"]),
        days=days,
        source="model",
    )


def get_weather(place: dict = PLACE, timeout: float = 8.0,
                max_age: float = 600.0) -> Weather:
    """取天气。优先未过期缓存 → 实况+预报 → 过期缓存。"""
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
        payload = _fetch_model(place, timeout)
        station = None
        if USE_STATION:
            try:
                station = _fetch_station(place.get("city_code", ""), timeout)
            except Exception:
                station = None
        w = _build(place, payload, station)

        # 实况没有体感温度，用模型的体感折算过来（保持温差）
        if station is not None:
            try:
                model_feels = float(payload["current"]["apparent_temperature"])
                model_temp = float(payload["current"]["temperature_2m"])
                w.feels = round(w.temp + (model_feels - model_temp), 1)
            except Exception:
                w.feels = w.temp

        with open(cache, "w", encoding="utf-8") as fh:
            json.dump(_to_json(w), fh, ensure_ascii=False)
        return w
    except Exception:
        if os.path.exists(cache):
            with open(cache, encoding="utf-8") as fh:
                return _from_json(json.load(fh), stale=True)
        raise


if __name__ == "__main__":
    w = get_weather(max_age=0)
    src = "实况观测" if w.source == "station" else "预报模型"
    print(f"{w.place} {w.temp:.1f}°C {w.desc} 体感{w.feels:.1f}° "
          f"湿度{w.humidity}% 风{w.wind_text or f'{w.wind:.1f}km/h'}"
          + (f" AQI {w.aqi}" if w.aqi is not None else "")
          + f"  [{src}{' · ' + w.obs_time if w.obs_time else ''}]"
          + ("  [缓存]" if w.stale else ""))
    for d in w.days:
        print(f"  {d.date} {d.week} {d.desc:<8} {d.tmin:.0f}~{d.tmax:.0f}°C"
              + (f" 降水{d.pop}%" if d.pop is not None else ""))
