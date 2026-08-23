import os, json
import tushare as ts

token = os.getenv('TUSHARE_TOKEN')
ts.set_token(token)
pro = ts.pro_api()

code = '000858.SZ'  # 五粮液

# Get annual income statements for years 2015-2024
income = []
for y in range(2015, 2025):
    df = pro.income(ts_code=code, start_date=f'{y}0101', end_date=f'{y}1231', fields='end_date,total_operate_income,n_income_attr_p')
    if not df.empty:
        row = df.iloc[-1]
        income.append({
            'year': y,
            'end_date': row['end_date'],
            'oper_rev': row['total_operate_income'],
            'net_profit': row['n_income_attr_p']
        })
print('Income data:', json.dumps(income, ensure_ascii=False, indent=2))

# Get financial indicators for ROE, margins
indicators = []
for y in range(2015, 2025):
    df = pro.fina_indicator(ts_code=code, start_date=f'{y}0101', end_date=f'{y}1231', fields='end_date,roe,grossprofit_margin,netprofit_margin,eps,bps,debt_to_assets,interest_cover')
    if not df.empty:
        row = df.iloc[-1]
        indicators.append({
            'year': y,
            'end_date': row['end_date'],
            'roe': row['roe'],
            'gross_margin': row['grossprofit_margin'],
            'net_margin': row['netprofit_margin'],
            'eps': row['eps'],
            'bps': row['bps'],
            'debt_to_assets': row['debt_to_assets'],
            'interest_cover': row['interest_cover']
        })
print('Indicators:', json.dumps(indicators, ensure_ascii=False, indent=2))