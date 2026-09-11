import os
import datetime
import requests

# ============ 設定區(從 GitHub Actions 的環境變數/密鑰讀取) ============
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# 股票代號,用逗號分隔。上市股票不用加前綴,上櫃股票代號前面加 "otc_"
# 例如: "2330,2317,otc_6488"  => 台積電、鴻海、上櫃的環球晶
STOCK_CODES = os.getenv("STOCK_CODES", "2330,2317").split(",")
# ==========================================================================

TAIPEI_TZ = datetime.timezone(datetime.timedelta(hours=8))


def build_query_string(codes):
    """把股票代號轉成 TWSE MIS API 需要的格式,例如 tse_2330.tw|otc_6488.tw"""
    parts = []
    for code in codes:
        code = code.strip()
        if not code:
            continue
        if code.startswith("otc_"):
            parts.append(f"otc_{code[4:]}.tw")
        else:
            parts.append(f"tse_{code}.tw")
    return "|".join(parts)


def fetch_stock_data(codes):
    """向台灣證交所 MIS API 查詢即時/最新股價資訊"""
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
    session.get("https://mis.twse.com.tw/stock/index.jsp", headers=headers, timeout=10)

    query = build_query_string(codes)
    url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
    resp = session.get(
        url, headers=headers, params={"ex_ch": query, "json": "1", "delay": "0"}, timeout=10
    )
    resp.raise_for_status()
    return resp.json().get("msgArray", [])


def format_stock_message(raw_list):
    """把 API 回傳的原始資料整理成好讀的訊息"""
    if not raw_list:
        return "⚠️ 目前查無資料,可能非交易時間或代號有誤。"

    today = datetime.datetime.now(TAIPEI_TZ).strftime("%Y/%m/%d")
    lines = [f"📈 **台股報價快報 — {today}**\n"]

    for item in raw_list:
        name = item.get("n", "未知")
        code = item.get("c", "?")
        latest = item.get("z", "-")
        prev_close = item.get("y", "-")
        open_price = item.get("o", "-")
        high = item.get("h", "-")
        low = item.get("l", "-")

        price_display = latest if latest not in ("-", "", None) else f"{prev_close}(昨收)"

        change_str = ""
        try:
            change = float(latest) - float(prev_close)
            pct = (change / float(prev_close)) * 100
            arrow = "🔺" if change > 0 else ("🔻" if change < 0 else "▪️")
            change_str = f"　{arrow} {change:+.2f} ({pct:+.2f}%)"
        except (ValueError, TypeError):
            pass

        lines.append(
            f"**{name} ({code})**\n"
            f"　現價: {price_display}{change_str}\n"
            f"　開盤: {open_price}　最高: {high}　最低: {low}　昨收: {prev_close}\n"
        )

    return "\n".join(lines)


def send_to_discord(message):
    """透過 Discord Webhook 發送訊息(不需要 Bot 帳號、不需要常駐連線)"""
    resp = requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
    resp.raise_for_status()


if __name__ == "__main__":
    if not WEBHOOK_URL:
        raise SystemExit("請先設定環境變數 DISCORD_WEBHOOK_URL")

    raw = fetch_stock_data(STOCK_CODES)
    msg = format_stock_message(raw)
    send_to_discord(msg)
    print("已推播訊息:\n", msg)
