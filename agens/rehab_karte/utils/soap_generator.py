import os
import socket
import threading

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


def is_online(host="8.8.8.8", port=53, timeout=2) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
        return True
    except OSError:
        return False


def is_available() -> bool:
    """SOAP生成機能が使用可能かチェック（ライブラリ・APIキー・オンライン）"""
    if not HAS_ANTHROPIC:
        return False
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    return is_online()


_SOAP_PROMPT = """\
あなたは理学療法士の臨床記録支援AIです。
以下の情報をもとに、SOAP形式のリハビリカルテを作成してください。

患者情報:
{patient_info}

S（主観的情報 / 患者の訴え）:
{subjective}

O（客観的情報 / 測定値・観察所見）:
{objective}

---
以下のSOAP形式で出力してください。

S: （患者の訴えを簡潔にまとめる）
O: （測定値・観察所見を整理する）
A: （理学療法士としての評価・臨床的推論。問題点を論理的に記載する）
P: （介入計画。具体的な治療内容・頻度を番号付きリストで記載する）

・専門的かつ簡潔な文体で記述してください
・個人名・施設名は記載しないでください
"""


def generate_soap(patient_info: str, subjective: str, objective: str) -> str:
    """
    Claude APIでSOAPカルテを生成して返す。
    呼び出し前に is_available() で確認すること。
    """
    if not HAS_ANTHROPIC:
        raise RuntimeError("anthropicライブラリが未インストールです。\npip install anthropic を実行してください。")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY が設定されていません。\n.env ファイルを確認してください。")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _SOAP_PROMPT.format(
        patient_info=patient_info,
        subjective=subjective,
        objective=objective,
    )
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def generate_soap_async(patient_info: str, subjective: str, objective: str,
                        on_success, on_error):
    """
    別スレッドでSOAP生成を実行する。UIスレッドをブロックしない。
    on_success(text: str) / on_error(msg: str) はメインスレッドで after() 経由で呼ぶこと。
    """
    def _run():
        try:
            result = generate_soap(patient_info, subjective, objective)
            on_success(result)
        except Exception as e:
            on_error(str(e))

    threading.Thread(target=_run, daemon=True).start()
