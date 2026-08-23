"""
扫描中国海油全部报告，检查数据一致性
"""
import json

# 1. 读取原始财务数据
data = json.load(open("local/cnooc_fin.json", "r", encoding="utf-8"))

# 按年报筛选
annuals = [r for r in data if "年报" in str(r.get("REPORT_DATE_NAME", ""))]
print("=== 原始年报数据 ===")
for r in annuals[:8]:
    name = r.get("REPORT_DATE_NAME", "")[:10]
    rev = r.get("TOTALOPERATEREVE", 0)
    np_val = r.get("PARENTNETPROFIT", 0)
    knp = r.get("KCFJCXSYJLR", 0)
    roe = r.get("ROEJQ", "")
    gm = r.get("XSMLL", "")
    npm = r.get("XSJLL", "")
    eps = r.get("EPSJB", "")
    ocf_ps = r.get("MGJYXJJE", "")
    bvps = r.get("BPS", "")
    print(f"  {name} 营收:{rev/1e8:.1f}亿 净利:{np_val/1e8:.1f}亿 扣非:{knp/1e8:.1f}亿 ROE:{roe} GM:{gm} NPM:{npm} EPS:{eps} OCF/PS:{ocf_ps} BVPS:{bvps}")

# 2. 读取行情数据
try:
    quote = json.load(open("local/cnooc_quote.json", "r", encoding="utf-8"))
    price = quote.get("f43", 0) / 100 if quote.get("f43") else "N/A"
    mcap = quote.get("f116", 0) / 1e8 if quote.get("f116") else "N/A"
    pe = quote.get("f162", 0) / 100 if quote.get("f162") else "N/A"
    pb = quote.get("f167", 0) / 100 if quote.get("f167") else "N/A"
    div_yield = quote.get("f173", 0) / 100 if quote.get("f173") else "N/A"
    high52 = quote.get("f44", 0) / 100 if quote.get("f44") else "N/A"
    low52 = quote.get("f45", 0) / 100 if quote.get("f45") else "N/A"
    print(f"\n=== 行情数据 ===")
    print(f"  价格:{price} 52周高:{high52} 52周低:{low52} 市值:{mcap}亿 PE:{pe} PB:{pb} 股息率:{div_yield}%")
except Exception as e:
    print(f"行情数据读取失败: {e}")

# 3. 检查报告中的数据与原始数据的差异
print("\n=== 数据一致性检查 ===")
# 报告中写的关键数据点：
# - 2024年报: 营收4190.7亿, 净利943.8亿, 扣非936.6亿, ROE 14.09%, GM 52.25%, NPM 22.4%, EPS 2.45
# - 2023年报: 营收4166.0亿, 净利1252.0亿, 扣非1156.4亿, ROE 19.55%, GM 52.6%, NPM 30.0%, EPS 2.64
# - 2022年报: 营收4585.9亿, 净利1429.1亿, 扣非1486.2亿, ROE 26.68%, GM 55.8%, NPM 31.2%, EPS 3.04

# 从原始数据中找对应年份验证
for r in annuals[:5]:
    name = str(r.get("REPORT_DATE_NAME", ""))[:10]
    rev = r.get("TOTALOPERATEREVE", 0)
    np_val = r.get("PARENTNETPROFIT", 0)
    knp = r.get("KCFJCXSYJLR", 0)
    roe = r.get("ROEJQ", "")
    gm = r.get("XSMLL", "")
    npm = r.get("XSJLL", "")
    eps = r.get("EPSJB", "")
    if "2024" in name:
        print(f"  2024年报验证: 营收{rev/1e8:.1f}(报告4190.7) 净利{np_val/1e8:.1f}(报告943.8) 扣非{knp/1e8:.1f}(报告936.6) ROE:{roe}(报告14.09%) GM:{gm}(报告52.25%) NPM:{npm}(报告22.4%) EPS:{eps}(报告2.45)")
    elif "2023" in name:
        print(f"  2023年报验证: 营收{rev/1e8:.1f}(报告4166.0) 净利{np_val/1e8:.1f}(报告1252.0) 扣非{knp/1e8:.1f}(报告1156.4) ROE:{roe}(报告19.55%) GM:{gm}(报告52.6%) NPM:{npm}(报告30.0%) EPS:{eps}(报告2.64)")
    elif "2022" in name:
        print(f"  2022年报验证: 营收{rev/1e8:.1f}(报告4585.9) 净利{np_val/1e8:.1f}(报告1429.1) 扣非{knp/1e8:.1f}(报告1486.2) ROE:{roe}(报告26.68%) GM:{gm}(报告55.8%) NPM:{npm}(报告31.2%) EPS:{eps}(报告3.04)")
    elif "2021" in name:
        print(f"  2021年报验证: 营收{rev/1e8:.1f}(报告2472.5) 净利{np_val/1e8:.1f}(报告703.2) 扣非{knp/1e8:.1f}(报告685.6) ROE:{roe}(报告15.38%) GM:{gm}(报告49.7%) NPM:{npm}(报告28.4%) EPS:{eps}(报告1.67)")
    elif "2020" in name:
        print(f"  2020年报验证: 营收{rev/1e8:.1f}(报告1504.0) 净利{np_val/1e8:.1f}(报告249.6) 扣非{knp/1e8:.1f}(报告201.8) ROE:{roe}(报告6.30%) GM:{gm}(报告46.6%) NPM:{npm}(报告16.6%) EPS:{eps}(报告0.60)")
