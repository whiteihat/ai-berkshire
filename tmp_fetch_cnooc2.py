"""
中国海油 - 获取现金流（算FCF）+ 当前行情
"""
import urllib.request
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://emweb.securities.eastmoney.com/"
}

# 1. 现金流量表（算FCF = OCF - CapEx）
cf_url = "https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_FINANCE_MAINFINADATA&sty=ALL&filter=(SECURITY_CODE=%22600938%22)&p=1&ps=20&sr=-1&st=REPORT_DATE&token=894050c76af8597a853f5b408b759f5d"
# Try alternative: cash flow specific endpoint
cf_url2 = "https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_F10_FINANCE_CASHFLOW&columns=ALL&filter=(SECURITY_CODE=%22600938%22)&pageNumber=1&pageSize=20&sortColumns=REPORT_DATE&sortTypes=-1&token=894050c76af8597a853f5b408b759f5d"

# 2. 行情数据
quote_url = "https://push2.eastmoney.com/api/qt/stock/get?secid=1.600938&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f55,f57,f58,f116,f117,f162,f167,f173"

results = {}

for name, url in [("cashflow", cf_url2), ("quote", quote_url)]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if name == "cashflow":
            if data.get("result") and data["result"].get("data"):
                records = data["result"]["data"]
                with open("local/cnooc_cf.json", "w", encoding="utf-8") as f:
                    json.dump(records, f, ensure_ascii=False, indent=2)
                print(f"现金流记录: {len(records)} 条")
                for r in records[:10]:
                    rn = r.get("REPORT_DATE_NAME", "")[:10]
                    ocf = r.get("SALES_SERVICES", 0) or 0
                    # Try different field names for operating cash flow
                    ocf2 = r.get("NETCASH_OPERATE", 0) or 0
                    capex = r.get("CONSTRUCT_LONG_ASSET", 0) or 0
                    print(f"  {rn} OCF:{ocf2/1e8:.1f}亿 CapEx:{capex/1e8:.1f}亿")
            else:
                print(f"现金流API返回: {json.dumps(data)[:300]}")
        else:
            if data.get("data"):
                d = data["data"]
                price = d.get("f43", 0) / 100 if d.get("f43") else "N/A"
                high52 = d.get("f44", 0) / 100 if d.get("f44") else "N/A"
                low52 = d.get("f45", 0) / 100 if d.get("f45") else "N/A"
                mcap = d.get("f116", 0) / 1e8 if d.get("f116") else "N/A"
                pe = d.get("f162", 0) / 100 if d.get("f162") else "N/A"
                pb = d.get("f167", 0) / 100 if d.get("f167") else "N/A"
                div_yield = d.get("f173", 0) / 100 if d.get("f173") else "N/A"
                print(f"行情: 价格={price} 52周高={high52} 52周低={low52} 市值={mcap}亿 PE={pe} PB={pb} 股息率={div_yield}%")
                with open("local/cnooc_quote.json", "w", encoding="utf-8") as f:
                    json.dump(d, f, ensure_ascii=False, indent=2)
            else:
                print(f"行情API返回: {json.dumps(data)[:300]}")
    except Exception as e:
        print(f"{name} 失败: {e}")
