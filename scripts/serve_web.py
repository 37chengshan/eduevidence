#!/usr/bin/env python3
"""scripts/serve_web.py — EduEvidence 落地页/静态资源预览服务器（CORS 开启）。

web/ 的营销落地页（landing.html 等）按架构是独立入口，不挂在
dashboard_server 路由下（P3 gate: /landing.html 必须 404）。本脚本以只读方式
静态托管 web/，并为所有响应加上 Access-Control-Allow-Origin: *，
使落地页与不同端口的 Web Studio 控制台之间能做跨源探测与互相跳转。

    python3 scripts/serve_web.py --host 127.0.0.1 --port 8877

首页入口：http://127.0.0.1:8877/landing.html
控制台：  http://127.0.0.1:8766/（scripts/dashboard_server.py）
"""
from __future__ import annotations

import argparse
import http.server
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"


class CORSStaticHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler + 允许跨源只读访问（探测/预览用）。"""

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8877)
    args = parser.parse_args()

    os.chdir(WEB_DIR)
    server = http.server.ThreadingHTTPServer(
        (args.host, args.port), CORSStaticHandler)
    print("=" * 60)
    print(f"🌐 EduEvidence 落地页 (CORS) running at http://{args.host}:{args.port}/")
    print(f"   首页      /landing.html")
    print(f"   控制台   http://{args.host}:8766/  (scripts/dashboard_server.py)")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
