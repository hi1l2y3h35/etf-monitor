import os
import re
import requests
from datetime import datetime

# ============ 配置 ============
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "")
THRESHOLD = 50.0  # 溢价率低于此值触发提醒，单位：%

ETF_LIST = [
    {"code": "sh513100", "name": "纳指ETF国泰"},
    {"code": "sz159941", "name": "纳指ETF广发"},
    {"code": "sh513390", "name": "纳指100ETF博时"},
    {"code": "sz159659", "name": "纳斯达克100ETF招商"},
    {"code": "sh513500", "name": "标普500ETF博时"},
    {"code": "sh513650", "name": "标普500ETF南方"},
    {"code": "sz159612", "name": "标普500ETF国泰"},
    {"code": "sz159655", "name": "标普500ETF华夏"},
]

# ============ 行情抓取 ============

def fetch_quotes(codes):
    url = "https://qt.gtimg.cn/q=" + ",".join(codes)
    resp = requests.get(url, timeout=15)
    resp.encoding = "gbk"

    results = {}
    for line in resp.text.strip().split("\n"):
        match = re.search(r'v_(\w+)="([^"]*)"', line)
        if not match:
            continue
        code = match.group(1)
        fields = match.group(2).split("~")

        price = float(fields[3]) if len(fields) > 3 and fields[3] else 0
        results[code] = {
            "name": fields[1] if len(fields) > 1 else "",
            "price": price,
            "prev_close": float(fields[4]) if len(fields) > 4 and fields[4] else 0,
            "change_pct": float(fields[32]) if len(fields) > 32 and fields[32] else 0,
            "iopv": 0,
        }

        # 尝试解析 IOPV
        for idx in [78, 79, 80, 33, 34]:
            if idx < len(fields):
                try:
                    v = float(fields[idx])
                    if 0 < v < 100 and price > 0 and abs(v - price) / price < 0.5:
                        results[code]["iopv"] = v
                        break
                except ValueError:
                    continue
    return results


# ============ 微信推送 ============

def send_wechat_push(title, content):
    if not PUSHPLUS_TOKEN:
        print("⚠️ 未设置 PUSHPLUS_TOKEN，跳过推送")
        return
    try:
        resp = requests.post(
            "https://www.pushplus.plus/send",
            json={
                "token": PUSHPLUS_TOKEN,
                "title": title,
                "content": content,
                "template": "markdown",
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("code") == 200:
            print(f"✅ 推送成功: {title}")
        else:
            print(f"❌ 推送失败: {data}")
    except Exception as e:
        print(f"❌ 推送异常: {e}")


# ============ 主逻辑 ============

def main():
    print(f"🕐 开始运行: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    codes = [item["code"] for item in ETF_LIST]
    quotes = fetch_quotes(codes)

    hits = []
    for item in ETF_LIST:
        q = quotes.get(item["code"])
        if not q or not q["price"] or not q["iopv"] or q["iopv"] <= 0:
            print(f"  ⚠️ {item['name']} 数据不完整，跳过")
            continue

        premium = (q["price"] - q["iopv"]) / q["iopv"] * 100
        name = q["name"] or item["name"]
        print(f"  📊 {name}: 价格={q['price']}, IOPV={q['iopv']}, 溢价率={premium:.2f}%")

        if premium < THRESHOLD:
            hits.append({
                "name": name,
                "price": q["price"],
                "iopv": q["iopv"],
                "premium": premium,
                "change_pct": q["change_pct"],
            })

    if not hits:
        print("  ✅ 所有ETF溢价率均高于阈值，无需提醒")
        return

    content = f"## ⚠️ ETF溢价率提醒\n\n"
    content += f"**触发条件**：溢价率低于 {THRESHOLD}%\n\n"
    content += f"**时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    content += "---\n\n"
    for h in hits:
        content += f"### {h['name']}\n\n"
        content += f"- 场内价格：**{h['price']:.3f}**\n"
        content += f"- IOPV：{h['iopv']:.4f}\n"
        content += f"- 溢价率：**{h['premium']:.2f}%**\n"
        content += f"- 当日涨跌幅：{h['change_pct']:+.2f}%\n\n"
    content += "> 数据仅供参考，不构成投资建议"

    send_wechat_push(f"ETF溢价提醒 · {len(hits)}只触发", content)


if __name__ == "__main__":
    main()
