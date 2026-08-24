#!/usr/bin/env python3
"""
魔芋平台 HTTP 中继服务。

Docker 容器无法直接与 uat.moyu.info 完成 TLS 握手（Docker 环境下的 TLS 兼容性问题），
此脚本运行在宿主机上，将 HTTP 请求透传到 https://uat.moyu.info 并返回结果。

用法：
    python3 moyu_relay.py              # 默认监听 0.0.0.0:18090
    python3 moyu_relay.py 18091        # 指定端口

Docker 容器通过 MOYU_API_URL=http://host.docker.internal:18090 访问。
"""

import http.server
import json
import sys
import urllib.request
import urllib.error
import logging

TARGET = "https://uat.moyu.info"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 18090

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("moyu-relay")


class RelayHandler(http.server.BaseHTTPRequestHandler):

    def _relay(self):
        url = TARGET + self.path
        body = None
        if "Content-Length" in self.headers:
            body = self.rfile.read(int(self.headers["Content-Length"]))

        headers = {}
        for key in ("Content-Type", "Authorization", "Accept"):
            if key in self.headers:
                headers[key] = self.headers[key]

        req = urllib.request.Request(url, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
        except urllib.error.HTTPError as e:
            resp_body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)
        except Exception as e:
            err = json.dumps({"error": str(e)}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)

    def do_GET(self):
        self._relay()

    def do_POST(self):
        self._relay()

    def log_message(self, fmt, *args):
        logger.info("%s %s", self.address_string(), fmt % args)


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), RelayHandler)
    logger.info("Moyu relay listening on 0.0.0.0:%d -> %s", PORT, TARGET)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.shutdown()
