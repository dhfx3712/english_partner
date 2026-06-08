import csv
import json
import time
import os
from requests import get
from requests.exceptions import RequestException, Timeout, ConnectionError

# ===================== 【核心：全部改成防封参数】=====================
CSV_PATH = "ecdict.csv"
OUT_JSON = "./datas/sentence_lib.json"
CHECK_POINT = "./datas/fetch_checkpoint.txt"

START_ID = 40001
BASE_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"

TIMEOUT = 15
# ===================== 【防封核心参数】=====================
REQ_DELAY = 2.0               # 间隔 2 秒（超级安全）
RETRY_DELAY = 3.0
MAX_RETRY = 1                # 只重试 1 次
BREAK_THRESHOLD = 5          # 放宽失败阈值
SLEEP_AFTER_FAIL = 20        # 熔断休眠 20 秒
# ===================== 【防封核心参数】=====================

sentence_list = []
current_id = START_ID
fail_count = 0

# ===================== 工具函数 =====================
def load_checkpoint() -> int:
    if os.path.exists(CHECK_POINT):
        try:
            with open(CHECK_POINT, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except:
            return 0
    return 0

def save_checkpoint(row_idx: int):
    with open(CHECK_POINT, "w", encoding="utf-8") as f:
        f.write(str(row_idx))

def get_word_level(tag_str: str) -> str:
    tag = str(tag_str).lower()
    if "cet6" in tag:
        return "CET6"
    elif "cet4" in tag:
        return "CET4"
    elif "gk" in tag:
        return "高考"
    elif "ky" in tag:
        return "考研"
    elif "zk" in tag:
        return "中考"
    return "CET4"

def fetch_example(word: str):
    url = BASE_URL.format(word.strip())
    for retry in range(MAX_RETRY + 1):
        try:
            resp = get(
                url,
                timeout=TIMEOUT,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                print("⚠️ 触发接口限流，休眠 30 秒！")
                time.sleep(30)
                return None
            else:
                return None
        except Exception:
            time.sleep(RETRY_DELAY)
    return None

# ===================== 主逻辑 =====================
def main():
    global current_id, fail_count
    start_row = load_checkpoint()
    print(f"🚀 【防封版】从第 {start_row} 行继续")
    print(f"⏱  请求间隔：{REQ_DELAY}s | 熔断休眠：{SLEEP_AFTER_FAIL}s")

    with open(CSV_PATH, "r", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        all_rows = list(reader)
        total_rows = len(all_rows)

        for row_idx, row in enumerate(all_rows):
            if row_idx < start_row:
                continue

            try:
                word = row.get("word", "").strip()
                tag = row.get("tag", "")
                trans = row.get("translation", "").strip()

                if len(word) < 2 or len(word) > 20:
                    save_checkpoint(row_idx)
                    time.sleep(REQ_DELAY)
                    continue

                # 熔断
                if fail_count >= BREAK_THRESHOLD:
                    print(f"⚠️ 连续失败，休眠 {SLEEP_AFTER_FAIL}s...")
                    time.sleep(SLEEP_AFTER_FAIL)
                    fail_count = 0

                api_data = fetch_example(word)
                if not api_data:
                    fail_count += 1
                    save_checkpoint(row_idx)
                    time.sleep(REQ_DELAY)
                    continue
                fail_count = 0

                # 提取例句
                example_sent = ""
                if isinstance(api_data, list) and len(api_data) > 0:
                    meanings = api_data[0].get("meanings", [])
                    for mean in meanings:
                        for d in mean.get("definitions", []):
                            exp = d.get("example", "").strip()
                            if exp and len(exp) > 6:
                                example_sent = exp
                                break
                        if example_sent:
                            break

                if not example_sent:
                    save_checkpoint(row_idx)
                    time.sleep(REQ_DELAY)
                    continue

                sentence_list.append({
                    "id": current_id,
                    "word_lower": word.lower(),
                    "sentence_en": example_sent,
                    "sentence_cn": trans,
                    "level": get_word_level(tag),
                    "scene": "API真实例句"
                })
                current_id += 1

                if len(sentence_list) % 20 == 0:
                    save_checkpoint(row_idx)
                    print(f"✅ 已抓取：{len(sentence_list)} 条")

                time.sleep(REQ_DELAY)

            except Exception as e:
                save_checkpoint(row_idx)
                time.sleep(REQ_DELAY)
                continue

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(sentence_list, f, ensure_ascii=False, indent=2)

    if os.path.exists(CHECK_POINT):
        os.remove(CHECK_POINT)

    print("="*60)
    print(f"🎉 完成！共 {len(sentence_list)} 条")
    print("="*60)

if __name__ == "__main__":
    main()
