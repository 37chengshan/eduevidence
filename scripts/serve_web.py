#!/usr/bin/env python3
"""scripts/serve_web.py — EduEvidence 介绍页/静态资源预览服务器（CORS 开启）。

`web/landing.html` 是独立的公开介绍页；正式研究控制台由
`scripts/dashboard_server.py` 提供 `web/studio/` 中的 Research Studio。
本脚本只用于只读预览介绍页和静态展示资源，不承载研究状态或控制台 API。

    python3 scripts/serve_web.py --host 127.0.0.1 --port 8877

介绍页：http://127.0.0.1:8877/landing.html
Research Studio：http://127.0.0.1:8765/studio/
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
    print(f"🌐 EduEvidence 介绍页预览 running at http://{args.host}:{args.port}/")
    print("   介绍页        /landing.html")
    print(f"   Research Studio http://{args.host}:8765/studio/  (scripts/dashboard_server.py)")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
