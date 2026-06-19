from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from quant.core.web import backtest_viz
from quant.core.web.control import (
    file_response_path,
    import_uploaded_fills,
    render_console_html,
    run_akshare_backtest,
    run_action,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local Personal Quant web console.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), QuantWebHandler)
    print(f"Personal Quant Web 控制台: http://{args.host}:{args.port}/")
    print("仅绑定本机地址；按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


class QuantWebHandler(BaseHTTPRequestHandler):
    server_version = "PersonalQuantWeb/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(render_console_html())
            return
        if parsed.path == "/api/status":
            from quant.apps import start

            self._send_json(start.latest_status_payload())
            return
        if parsed.path == "/backtest":
            self._send_html(backtest_viz.render_backtest_html())
            return
        if parsed.path.startswith("/file/"):
            self._send_file(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/action/"):
            action = unquote(parsed.path.removeprefix("/action/"))
            try:
                result = run_action(action)
                self._send_html(
                    render_console_html(
                        f"任务完成: {action}，状态 {result.status}，返回码 {result.return_code}"
                    )
                )
            except Exception as exc:
                self._send_html(render_console_html(f"任务失败: {exc}"), HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/upload-fills":
            try:
                filename, content, fields = self._parse_multipart()
                result = import_uploaded_fills(
                    filename,
                    content,
                    skip_refresh=fields.get("skip_refresh") == "1",
                )
                self._send_html(
                    render_console_html(
                        f"成交导入完成: 状态 {result.status}，返回码 {result.return_code}"
                    )
                )
            except Exception as exc:
                self._send_html(render_console_html(f"上传失败: {exc}"), HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/akshare-backtest":
            try:
                fields = self._parse_urlencoded()
                result = run_akshare_backtest(
                    start_date=fields.get("start_date", ""),
                    end_date=fields.get("end_date", ""),
                    rebalance=fields.get("rebalance", "weekly"),
                    limit=fields.get("limit", ""),
                )
                self._send_html(
                    render_console_html(
                        f"AkShare 全市场回测完成: 状态 {result.status}，返回码 {result.return_code}"
                    )
                )
            except Exception as exc:
                self._send_html(render_console_html(f"AkShare 全市场回测失败: {exc}"), HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == '/reset-paper':
            from quant.core.web.control import reset_paper_trading
            try:
                fields = self._parse_urlencoded()
                initial_cash = float(fields.get('initial_cash', '1000000'))
                result = reset_paper_trading(initial_cash=initial_cash)
                self._send_html(
                    render_console_html(
                        f'模拟盘已重置，初始资金 {initial_cash:,.0f}'
                    )
                )
            except Exception as exc:
                self._send_html(render_console_html(f'重置失败: {exc}'), HTTPStatus.BAD_REQUEST)
            return
        self._send_text("Not found", HTTPStatus.NOT_FOUND)

    def _parse_urlencoded(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        parsed = parse_qs(body)
        return {key: values[0] if values else "" for key, values in parsed.items()}

    def _parse_multipart(self) -> tuple[str, bytes, dict[str, str]]:
        content_type = self.headers.get("Content-Type", "")
        marker = "boundary="
        if marker not in content_type:
            raise ValueError("expected multipart/form-data")
        boundary = content_type.split(marker, 1)[1].strip().strip('"')
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        delimiter = ("--" + boundary).encode()
        fields: dict[str, str] = {}
        upload_name = ""
        upload_content = b""
        for part in body.split(delimiter):
            part = part.strip(b"\r\n")
            if not part or part == b"--":
                continue
            headers_raw, _, content = part.partition(b"\r\n\r\n")
            header_text = headers_raw.decode("utf-8", errors="replace")
            disposition = next(
                (line for line in header_text.splitlines() if line.lower().startswith("content-disposition")),
                "",
            )
            name = _header_param(disposition, "name")
            filename = _header_param(disposition, "filename")
            content = content.rstrip(b"\r\n")
            if filename:
                upload_name = Path(filename).name
                upload_content = content
            elif name:
                fields[name] = content.decode("utf-8", errors="replace")
        if not upload_content:
            raise ValueError("no uploaded CSV file")
        return upload_name, upload_content, fields

    def _send_file(self, url_path: str) -> None:
        try:
            path = file_response_path(unquote(url_path))
        except FileNotFoundError:
            self._send_text("File not found", HTTPStatus.NOT_FOUND)
            return
        except PermissionError:
            self._send_text("Forbidden", HTTPStatus.FORBIDDEN)
            return
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_bytes(text.encode("utf-8"), "text/html; charset=utf-8", status)

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_bytes(
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

    def _send_text(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_bytes(text.encode("utf-8"), "text/plain; charset=utf-8", status)

    def _send_bytes(self, data: bytes, content_type: str, status: HTTPStatus) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        return


def _header_param(header: str, name: str) -> str:
    prefix = name + "="
    for part in header.split(";"):
        part = part.strip()
        if part.startswith(prefix):
            return part[len(prefix) :].strip().strip('"')
    return ""


if __name__ == "__main__":
    main()
