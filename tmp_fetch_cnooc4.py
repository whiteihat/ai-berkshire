"""
中国海油 - 获取现金流（尝试不同API）
"""
import urllib.request
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://emweb.securities.eastmoney.com/"
}

# 方法1: 用RPT_F10_FINANCE_MAINFINADATA包含的现金流字段
# 之前拿到的数据中可能已有OCF字段，先看看有哪些字段
data = json.load(open("local/cnooc_fin.json", "r", encoding="utf-8"))
# 打印所有字段名和2024年报的值
annual = [r for r in data if "2024" in str(r.get("REPORT_DATE_NAME", "")) and "年报" in str(r.get("REPORT_DATE_NAME", ""))]
if annual:
    r = annual[0]
    print("=== 2024年报所有字段 ===")
    for k, v in r.items():
        if v and v != 0 and v != "" and v != "null":
            print(f"  {k}: {v}")

# 方法2: 用现金流量表专用接口 - 不同报表名
urls = [
    ("RPT_F10_FINANCE_GCASHFLOW", "https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_F10_FINANCE_GCASHFLOW&columns=ALL&filter=(SECURITY_CODE=%22600938%22)&pageNumber=1&pageSize=5&sortColumns=REPORT_DATE&sortTypes=-1&token=894050c76af8597a853f5b408b759f5d"),
    ("RPTA_WEB_CASHFLOW_NEW", "https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPTA_WEB_CASHFLOW_NEW&columns=ALL&filter=(SECURITY_CODE=%22600938%22)&pageNumber=1&pageSize=5&sortColumns=REPORT_DATE&sortTypes=-1&token=894050c76af8597a853f5b408b759f5d"),
]

for name, url in urls:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            d = json.loads(resp.read().decode("utf-8"))
        if d.get("result") and d["result"].get("data"):
            records = d["result"]["data"]
            print(f"\n=== {name}: {len(records)} records ===")
            r = records[0]
            for k, v in r.items():
                if v and v != 0 and v != "":
                    val = v/1e8 if isinstance(v, (int, float)) and abs(v) > 1e6 else v
                    print(f"  {k}: {val}")
            break
        else:
            print(f"{name}: {d.get('message', 'no data')}")
    except Exception as e:
        print(f"{name}: {e}")
