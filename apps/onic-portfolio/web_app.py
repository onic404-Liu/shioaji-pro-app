"""Loopback-only web UI with per-process authorization and no external assets."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import secrets
import threading
import webbrowser
from trading_service import Workspace, InputError

BASE = Path(__file__).parent


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, workspace=None, token=None):
        self.workspace = workspace or Workspace(inventory_only=True)
        self.token = token or secrets.token_urlsafe(32)
        super().__init__(address, Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Request bodies, credentials and account data never enter access logs.

    def reply(self, status, value, content_type='application/json; charset=utf-8'):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8') if isinstance(value, dict) else value
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self, mutation=False):
        if self.headers.get('Host') != self.server.origin.removeprefix('http://'):
            self.reply(403, {'error': '連線來源無效，請從本機啟動入口開啟。'})
            return False
        expected = 'Bearer ' + self.server.token
        if not hmac.compare_digest(self.headers.get('Authorization', ''), expected):
            self.reply(401, {'error': '本機連線已失效。請重新用啟動檔開啟介面。'})
            return False
        if mutation and self.headers.get('Origin') != self.server.origin:
            self.reply(403, {'error': '拒絕非本機介面的操作。'})
            return False
        return True

    def do_GET(self):
        if self.path == '/api/state':
            if self.authorized():
                try:
                    with self.server.workspace.lock:
                        self.reply(200, self.server.workspace.state())
                except Exception:
                    self.reply(500, {'error': '無法取得狀態，請重新整理或重啟本機服務。'})
            return
        allowed = {'/': ('index.html', 'text/html; charset=utf-8'),
                   '/app.css': ('app.css', 'text/css; charset=utf-8'),
                   '/app.js': ('app.js', 'text/javascript; charset=utf-8')}
        if self.path not in allowed or self.headers.get('Host') != self.server.origin.removeprefix('http://'):
            self.reply(404, {'error': '找不到頁面。'})
            return
        name, mime = allowed[self.path]
        self.reply(200, (BASE / 'web' / name).read_bytes(), mime)

    def do_POST(self):
        if not self.authorized(mutation=True):
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 16384 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('請求格式無效。')
            data = json.loads(self.rfile.read(size).decode('utf-8'))
            if not isinstance(data, dict):
                raise ValueError('請求格式無效。')
            if not self.path.startswith('/api/'):
                raise ValueError('未知操作。')
            route = self.path[5:]
            if route == 'shutdown':
                with self.server.workspace.lock:
                    self.server.workspace.disconnect()
                self.reply(200, {'stopped': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            result = self.server.workspace.dispatch(route, data)
            self.reply(200, result)
        except InputError as exc:
            self.reply(400, {'error': str(exc)})
        except ValueError:
            self.reply(400, {'error': '輸入格式無效，請檢查欄位。'})
        except Exception as exc:
            kind = type(exc).__name__
            message = {'AuthError': '登入驗證失敗。請檢查金鑰、IP 限制、有效期限與簽署。',
                       'TokenError': '金鑰驗證失敗，請重新複製完整的 Key 與 Secret Key。',
                       'TimeoutError': '永豐服務回覆逾時。若剛送過委託，請先查詢回報，勿重送。',
                       'AccountNotSignError': '證券 API 同意書尚未生效，請確認簽署狀態。'}.get(kind)
            self.reply(500, {'error': message or f'操作未完成（{kind}）。請檢查連線與 API 權限。'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        server = Server(('127.0.0.1', args.port))
    except OSError:
        print('本機服務埠已被占用；請關閉先前的服務視窗後再啟動。')
        return
    url = server.origin + '/#' + server.token
    if args.no_browser:
        print(json.dumps({'url': url}), flush=True)
    else:
        webbrowser.open(url, new=2)
        print('投資簿已啟動。請保留這個視窗；關閉視窗會停止行情與提醒。', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.workspace.disconnect()
        server.server_close()


if __name__ == '__main__':
    main()
