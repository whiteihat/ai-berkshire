"""
中国海油 - 分红数据 + 历史数据
"""
import urllib.request
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://emweb.securities.eastmoney.com/"
}

# 分红数据
div_url = "https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_SHAREBONUS_DET&columns=ALL&filter=(SECURITY_CODE=%22600938%22)&pageNumber=1&pageSize=20&sortColumns=EX_DIVIDEND_DATE&sortTypes=-1&token=894050c76af8597a853f5b408b759f5d"

req = urllib.request.Request(div_url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("result") and data["result"].get("data"):
        records = data["result"]["data"]
        print(f"分红记录: {len(records)} 条")
        for r in records[:10]:
            year = r.get("REPORT_DATE_NAME", "")[:10]
            plan = r.get("PLAN_NOTICE_DATE", "")[:10]
            bonus = r.get("BONUS_IT_RATIO", 0) or 0
            bonus2 = r.get("PRETAX_BONUS_RMB", 0) or 0
            ex_date = r.get("EX_DIVIDEND_DATE", "")[:10] if r.get("EX_DIVIDEND_DATE") else ""
            print(f"  {year} 每股分红:{bonus2}元 除权日:{ex_date}")
    else:
        print(f"分红API: {json.dumps(data)[:500]}")
except Exception as e:
    print(f"分红失败: {e}")

# 获取历史年度数据（看5年ROE趋势）
print("\n--- 历史年报ROE ---")
main_url = "https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_FINANCE_MAINFINADATA&sty=ALL&filter=(SECURITY_CODE=%22600938%22)(REPORT_TYPE=%22年报%22)&p=1&ps=10&sr=-1&st=REPORT_DATE&token=894050c76af8597a853f5b408b759f5d"
req2 = urllib.request.Request(main_url, headers=headers)
try:
    with urllib.request.urlopen(req2, timeout=30) as resp:
        data2 = json.loads(resp.read().decode("utf-8"))
    if data2.get("success") and data2.get("result") and data2["result"].get("data"):
        for r in data2["result"]["data"]:
            name = r.get("REPORT_DATE_NAME", "")[:10]
            rev = r.get("TOTALOPERATEREVE", 0)
            np_val = r.get("PARENTNETPROFIT", 0)
            knp = r.get("KCFJCXSYJLR", 0)
            roe = r.get("ROEJQ", "")
            gm = r.get("XSMLL", "")
            npm = r.get("XSJLL", "")
            eps = r.get("EPSJB", "")
            print(f"  {name} 营收:{rev/1e8:.1f}亿 净利:{np_val/1e8:.1f}亿 扣非:{knp/1e8:.1f}亿 ROE:{roe} GM:{gm} NPM:{npm} EPS:{eps}")
except Exception as e:
    print(f"历史数据失败: {e}")
