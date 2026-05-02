"""
Threads アクセストークン取得スクリプト
実行すると自動でブラウザが開き、トークンを取得して .env に保存します
"""
import http.server
import json
import os
import threading
import urllib.parse
import urllib.request
import webbrowser

APP_ID = input("App ID を入力してください: ").strip()
APP_SECRET = input("App Secret を入力してください: ").strip()

REDIRECT_URI = "http://localhost:8888"
SCOPE = "threads_basic,threads_content_publish,threads_manage_insights"

auth_url = (
    f"https://threads.net/oauth/authorize"
    f"?client_id={APP_ID}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&scope={SCOPE}"
    f"&response_type=code"
)

code_holder = {}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            code_holder["code"] = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write("✅ 認証完了！このタブを閉じてターミナルに戻ってください。".encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write("エラー: codeが取得できませんでした".encode("utf-8"))

    def log_message(self, format, *args):
        pass  # ログ非表示

server = http.server.HTTPServer(("localhost", 8888), Handler)
t = threading.Thread(target=server.handle_request)
t.start()

print("\nブラウザが開きます。Threadsアカウントでログインして許可してください...")
webbrowser.open(auth_url)
t.join()

if "code" not in code_holder:
    print("❌ コードが取得できませんでした")
    exit(1)

code = code_holder["code"]
print(f"✅ コード取得: {code[:20]}...")

# コードをトークンに交換
data = urllib.parse.urlencode({
    "client_id": APP_ID,
    "client_secret": APP_SECRET,
    "grant_type": "authorization_code",
    "redirect_uri": REDIRECT_URI,
    "code": code,
}).encode()

req = urllib.request.Request(
    "https://graph.threads.net/oauth/access_token",
    data=data,
    method="POST"
)

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
except Exception as e:
    print(f"❌ トークン取得失敗: {e}")
    exit(1)

access_token = result.get("access_token")
user_id = str(result.get("user_id", ""))

if not access_token:
    print(f"❌ レスポンス: {result}")
    exit(1)

print(f"✅ アクセストークン取得完了")
print(f"✅ ユーザーID: {user_id}")

# .env に書き込む
env_path = os.path.join(os.path.dirname(__file__), ".env")
with open(env_path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "THREADS_ACCESS_TOKEN=",
    f"THREADS_ACCESS_TOKEN={access_token}"
) if "THREADS_ACCESS_TOKEN=" in content and f"THREADS_ACCESS_TOKEN={access_token}" not in content else content

content = content.replace(
    "THREADS_USER_ID=",
    f"THREADS_USER_ID={user_id}"
) if "THREADS_USER_ID=" in content and f"THREADS_USER_ID={user_id}" not in content else content

with open(env_path, "w", encoding="utf-8") as f:
    f.write(content)

print("\n✅ .env に保存しました！")
print(f"  THREADS_ACCESS_TOKEN={access_token[:30]}...")
print(f"  THREADS_USER_ID={user_id}")
print("\n次のコマンドで動作確認してください:")
print("  python main.py --status")
