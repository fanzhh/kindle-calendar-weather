#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""面板 HTTP 服务：Kindle 从这里拉取 600×800 的屏保图。

    GET /            预览页（浏览器打开即可看效果）
    GET /dash.png    面板图（Kindle 拉这张）
    GET /health      状态 JSON

默认监听 0.0.0.0:8099，局域网内可访问。图片在内存里缓存，
超过 REFRESH_SECONDS 才会重新渲染，避免每次请求都联网取天气。
"""

import argparse
import io
import json
import os
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from render import dash
from render.weather import get_weather

STATE = {"png": None, "rendered_at": 0.0, "stale": False, "error": None}
VARIANTS = {}            # banner 文字 -> (png bytes, rendered_at)
LOCK = threading.Lock()
REFRESH_SECONDS = 600


def _render_png(force: bool = False, banner: str = "") -> bytes:
    """渲染并缓存 PNG；force=True 时忽略缓存。banner 非空时输出带横幅的变体。"""
    if banner:
        hit = VARIANTS.get(banner)
        if hit and not force and time.time() - hit[1] < REFRESH_SECONDS:
            return hit[0]
        with LOCK:
            w = get_weather(max_age=REFRESH_SECONDS)
            img = dash.render(w, banner=banner)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            VARIANTS[banner] = (buf.getvalue(), time.time())
            return VARIANTS[banner][0]

    now = time.time()
    if not force and STATE["png"] and now - STATE["rendered_at"] < REFRESH_SECONDS:
        return STATE["png"]
    with LOCK:
        if not force and STATE["png"] and time.time() - STATE["rendered_at"] < REFRESH_SECONDS:
            return STATE["png"]
        try:
            w = get_weather(max_age=REFRESH_SECONDS)
            img = dash.render(w)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            STATE["png"] = buf.getvalue()
            STATE["rendered_at"] = time.time()
            STATE["stale"] = w.stale
            STATE["error"] = None
        except Exception as exc:                     # 保留上一张图，不让面板黑掉
            STATE["error"] = f"{type(exc).__name__}: {exc}"
            if not STATE["png"]:
                raise
        return STATE["png"]


PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Kindle 日历面板</title>
<style>
  body {{ margin:0; background:#e9e9e9; font:14px/1.6 -apple-system,sans-serif;
         display:flex; flex-direction:column; align-items:center; padding:24px; }}
  img  {{ width:600px; height:800px; image-rendering:pixelated;
         border:1px solid #bbb; background:#fff; }}
  p    {{ color:#555; }}
</style></head>
<body>
  <img src="/dash.png?t={ts}" alt="dash">
  <p>600×800 · 每次刷新页面重新取图 · <span id="st">{stamp}</span></p>
</body></html>
"""

# Kindle 自带的「体验版浏览器」用这个页面：无边框、无滚动条、定时自刷新
KIOSK = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=600,initial-scale=1">
<meta http-equiv="refresh" content="{refresh}">
<title>日历</title>
<style>
  html, body {{ margin:0; padding:0; background:#fff; overflow:hidden; }}
  img {{ display:block; width:600px; height:800px; border:0; }}
</style></head>
<body><img src="/dash.png?t={ts}" alt=""></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "kindle-dash/1.0"

    def _send(self, code: int, body: bytes, ctype: str, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        force = url.path == "/dash.png" and query.get("force", ["0"])[0] in ("1", "true")
        banner = query.get("banner", [""])[0][:40]

        if url.path in ("/", "/index.html"):
            stamp = (datetime.fromtimestamp(STATE["rendered_at"]).strftime("%Y-%m-%d %H:%M:%S")
                     if STATE["rendered_at"] else "尚未渲染")
            html = PAGE.format(ts=int(time.time()), stamp=stamp).encode("utf-8")
            self._send(200, html, "text/html; charset=utf-8")
            return

        if url.path in ("/kiosk", "/kiosk.html"):
            html = KIOSK.format(ts=int(time.time()), refresh=max(300, REFRESH_SECONDS)).encode("utf-8")
            self._send(200, html, "text/html; charset=utf-8")
            return

        if url.path == "/health":
            body = json.dumps({
                "ok": STATE["png"] is not None,
                "rendered_at": (datetime.fromtimestamp(STATE["rendered_at"]).isoformat()
                                if STATE["rendered_at"] else None),
                "stale_weather": STATE["stale"],
                "last_error": STATE["error"],
                "size": len(STATE["png"]) if STATE["png"] else 0,
            }, ensure_ascii=False, indent=2).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return

        if url.path == "/dash.png":
            try:
                png = _render_png(force=force, banner=banner)
            except Exception as exc:
                self._send(500, f"render failed: {exc}".encode("utf-8"),
                           "text/plain; charset=utf-8")
                return
            self._send(200, png, "image/png")
            return

        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, fmt, *args):     # 静音访问日志，避免刷屏
        pass


def main():
    global REFRESH_SECONDS
    ap = argparse.ArgumentParser(description="Kindle 日历面板服务")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--refresh", type=int, default=600, help="图片缓存秒数，默认 600")
    args = ap.parse_args()
    REFRESH_SECONDS = args.refresh

    try:
        _render_png(force=True)
        print(f"预热完成，PNG {len(STATE['png']) / 1024:.1f} KB")
    except Exception as exc:
        print(f"预热失败（服务照常启动，稍后重试）: {exc}")

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"监听 http://{args.host}:{args.port}/dash.png")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n退出")


if __name__ == "__main__":
    main()
