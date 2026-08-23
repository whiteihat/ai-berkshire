import json
with open('e:/Code/Python/src-code/ai-berkshire/local/gnjt_fin.json','r',encoding='utf-8') as f:
    data=json.load(f)
items=data['result']['data']
print(f'Records: {len(items)}')
print()
print('=== Annual Reports ===')
for item in items:
    rpt=item.get('REPORT_TYPE','')
    if rpt!='年报': continue
    d=item.get('REPORT_DATE_NAME','')
    r=(item.get('TOTALOPERATEREVE') or 0)/1e8
    n=(item.get('PARENTNETPROFIT') or 0)/1e8
    kcfj=(item.get('KCFJCXSYJLR') or 0)/1e8
    roe=item.get('ROEJQ') or 0
    gm=item.get('XSMLL') or 0
    npm=item.get('XSJLL') or 0
    eps=item.get('EPSJB') or 0
    bvps=item.get('BPS') or 0
    debt=item.get('ZCFZL') or 0
    ocf=(item.get('NETCASH_OPERATE_PK') or 0)/1e8
    fcf=(item.get('FCFF_FORWARD') or 0)/1e8
    ic=item.get('INTSTCOVRATE') or 0
    ta=(item.get('TOTAL_ASSETS_PK') or 0)/1e8
    tl=(item.get('LIABILITY') or 0)/1e8
    shares=(item.get('TOTAL_SHARE') or 0)/1e8
    print(f'{d}: Rev={r:.1f} NP={n:.1f} KCFJ={kcfj:.1f} ROE={roe:.1f}% GM={gm:.1f}% NPM={npm:.1f}% EPS={eps:.3f} BPS={bvps:.3f} Debt={debt:.1f}% OCF={ocf:.1f} FCFF={fcf:.1f} ICov={ic:.0f}x TA={ta:.0f} TL={tl:.0f} Shares={shares:.2f}yi')

print()
print('=== Recent Quarterly ===')
for item in items[:5]:
    rpt=item.get('REPORT_TYPE','')
    if rpt=='年报': continue
    d=item.get('REPORT_DATE_NAME','')
    r=(item.get('TOTALOPERATEREVE') or 0)/1e8
    n=(item.get('PARENTNETPROFIT') or 0)/1e8
    roe=item.get('ROEJQ') or 0
    gm=item.get('XSMLL') or 0
    npm=item.get('XSJLL') or 0
    eps=item.get('EPSJB') or 0
    print(f'{d}: Rev={r:.1f} NP={n:.1f} ROE={roe:.1f}% GM={gm:.1f}% NPM={npm:.1f}% EPS={eps:.3f}')
