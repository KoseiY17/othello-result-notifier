import json
import os
import re
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

RESULTS_URL = "https://www.othello.gr.jp/competition_result"
STATE_FILE = Path("known_results.json")
NTFY_SERVER = "https://ntfy.sh"


def fetch_html(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Othello Result Notifier)"
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def get_results():
    html = fetch_html(RESULTS_URL)

    # 大会結果ページへのリンクを抽出
    pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']*/competition_result/\d+/?)[^"\']*["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    results = []

    for href, title_html in pattern.findall(html):
        title = re.sub(r"<[^>]+>", "", title_html)
        title = re.sub(r"\s+", " ", title).strip()

        url = urljoin(RESULTS_URL, href)

        match = re.search(r"/competition_result/(\d+)", url)
        if not match:
            continue

        result_id = match.group(1)

        if not any(r["id"] == result_id for r in results):
            results.append(
                {
                    "id": result_id,
                    "title": title,
                    "url": url,
                }
            )

    if not results:
        raise RuntimeError("大会結果を取得できませんでした。サイト構造が変更された可能性があります。")

    return results


def load_known_results():
    if not STATE_FILE.exists():
        return set()

    with STATE_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return set(data)


def save_known_results(results):
    ids = [r["id"] for r in results]

    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False, indent=2)


def send_notification(result):
    topic = os.environ.get("NTFY_TOPIC")

    if not topic:
        raise RuntimeError("NTFY_TOPIC が設定されていません。")

    payload = {
        "topic": topic,
        "title": "日本オセロ連盟 大会結果",
        "message": f"{result['title']}が更新されました",
        "click": result["url"],
        "tags": ["game_die"],
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(
        NTFY_SERVER,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def main():
    results = get_results()
    known = load_known_results()

    # 初回実行
    # 現在掲載されている結果を記録するだけで通知しない
    if not STATE_FILE.exists():
        save_known_results(results)
        print(f"初回登録：{len(results)}件を記録しました。通知は行いません。")
        return

    new_results = [r for r in results if r["id"] not in known]

    if not new_results:
        print("新しい大会結果はありません。")
        return

    # 古いものから順番に通知
    for result in reversed(new_results):
        print(f"新規大会結果：{result['title']}")
        send_notification(result)

    save_known_results(results)


if __name__ == "__main__":
    main()
