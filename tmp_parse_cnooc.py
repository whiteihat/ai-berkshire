"""
Parse CNOOC financial data
"""
import json

data = json.load(open("local/cnooc_fin.json", "r", encoding="utf-8"))
for r in data[:12]:
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
    print(f"{name} 营收:{rev/1e8:.1f}亿 净利:{np_val/1e8:.1f}亿 扣非:{knp/1e8:.1f}亿 ROE:{roe} GM:{gm} NPM:{npm} EPS:{eps} OCF/PS:{ocf_ps} BVPS:{bvps}")
