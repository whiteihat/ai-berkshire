"""
中国海油 (600938) 财务数据获取
"""
import urllib.request
import json
import sys

def fetch_cnooc():
    url = "https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_FINANCE_MAINFINADATA&sty=ALL&filter=(SECURITY_CODE=%22600938%22)&p=1&ps=50&sr=-1&st=REPORT_DATE&token=894050c76af8597a853f5b408b759f5d"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://emweb.securities.eastmoney.com/"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if data.get("success") and data.get("result") and data["result"].get("data"):
            records = data["result"]["data"]
            with open("local/cnooc_fin.json", "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            print(f"获取到 {len(records)} 条财务记录")
            # 打印关键数据
            for r in records[:20]:
                print(f"期:{r.get('REPORT_DATE_NAME','')[:10]} 营收:{r.get('TOTAL_OPERATE_INCOME',0)/1e8:.1f}亿 净利润:{r.get('PARENT_NETPROFIT',0)/1e8:.1f}亿 扣非:{r.get('DEDUCT_PARENT_NETPROFIT',0)/1e8:.1f}亿 经营现金流:{r.get('TOTAL_OPERATE_CASH_FLOW',0)/1e8:.1f}亿 EPS:{r.get('BASIC_EPS','')}")
        else:
            print("未获取到数据")
    except Exception as e:
        print(f"获取失败: {e}")

fetch_cnooc()
