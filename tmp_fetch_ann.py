#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取国电电力（600795.SH）公告信息的临时脚本
数据源：东方财富网、巨潮资讯网
"""

import requests
import json
import sys
from datetime import datetime, timedelta

# 设置输出编码为UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

def fetch_eastmoney_announcements(stock_code, start_date, end_date):
    """从东方财富网获取公告列表"""
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {
        "sr": "-1",
        "page_size": "50",
        "page_index": "1",
        "ann_type": "A",
        "client_source": "web",
        "stock_list": stock_code,
        "f_node": "0",
        "s_node": "0"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://data.eastmoney.com/",
        "Accept": "application/json, text/plain, */*"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("success") and data.get("data") and data["data"].get("list"):
            return data["data"]["list"]
        else:
            print(f"东方财富网API返回异常: {data}")
            return []
    except Exception as e:
        print(f"东方财富网请求失败: {e}")
        return []

def get_announcement_detail(art_code):
    """获取公告详细内容"""
    url = f"https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {
        "sr": "-1",
        "page_size": "1",
        "page_index": "1",
        "ann_type": "A",
        "client_source": "web",
        "stock_list": "600795",
        "f_node": "0",
        "s_node": "0",
        "art_code": art_code
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://data.eastmoney.com/",
        "Accept": "application/json, text/plain, */*"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("success") and data.get("data") and data["data"].get("list"):
            return data["data"]["list"][0] if data["data"]["list"] else None
        return None
    except Exception as e:
        print(f"获取公告详情失败: {e}")
        return None

def fetch_cninfo_announcements(stock_code, start_date, end_date):
    """从巨潮资讯网获取公告列表"""
    url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.cninfo.com.cn/",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json, text/plain, */*"
    }

    # 计算时间戳
    now = datetime.now()
    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
    end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

    data = {
        "stock": stock_code,
        "tabName": "fulltext",
        "pageNum": "1",
        "pageSize": "30",
        "column": "szse",  # 深交所，600开头是上交所，但巨潮通用
        "category": "",
        "plate": "",
        "seDate": f"{start_date}~{end_date}"
    }

    try:
        response = requests.post(url, data=data, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("hasAnnouncement") and result.get("announcements"):
            return result["announcements"]
        else:
            print(f"巨潮资讯网API返回异常: {result}")
            return []
    except Exception as e:
        print(f"巨潮资讯网请求失败: {e}")
        return []

def format_date(date_str):
    """格式化日期"""
    if not date_str:
        return "未知"
    try:
        # 东方财富网格式：2026-08-20 10:30:00
        if " " in str(date_str):
            return str(date_str).split(" ")[0]
        # 巨潮资讯网格式：1692500000000 (时间戳)
        ts = int(date_str) / 1000
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except:
        return str(date_str)

def main():
    stock_code = "600795"
    start_date = "2026-08-06"
    end_date = "2026-08-20"

    print(f"=" * 80)
    print(f"国电电力（{stock_code}.SH）公告信息查询")
    print(f"查询期间：{start_date} 至 {end_date}")
    print(f"=" * 80)

    # 从东方财富网获取
    print(f"\n【数据源1：东方财富网】")
    eastmoney_anns = fetch_eastmoney_announcements(stock_code, start_date, end_date)

    if eastmoney_anns:
        # 筛选指定日期范围内的公告
        filtered_anns = []
        for ann in eastmoney_anns:
            ann_date = format_date(ann.get("notice_date", ""))
            if start_date <= ann_date <= end_date:
                filtered_anns.append(ann)

        print(f"在 {start_date} 至 {end_date} 期间找到 {len(filtered_anns)} 条公告：")
        for i, ann in enumerate(filtered_anns, 1):
            title = ann.get("title", "无标题")
            ann_date = format_date(ann.get("notice_date", ""))
            ann_type = ann.get("ann_type", "")
            art_code = ann.get("art_code", "")
            print(f"{i:2d}. [{ann_date}] {title}")
            if ann_type:
                print(f"    类型: {ann_type}")
            if art_code:
                print(f"    代码: {art_code}")
    else:
        print("未找到公告或请求失败")

    # 从巨潮资讯网获取
    print(f"\n【数据源2：巨潮资讯网】")
    cninfo_anns = fetch_cninfo_announcements(stock_code, start_date, end_date)

    if cninfo_anns:
        print(f"找到 {len(cninfo_anns)} 条公告：")
        for i, ann in enumerate(cninfo_anns[:20], 1):
            title = ann.get("announcementTitle", "无标题")
            ann_date = format_date(ann.get("announcementTime", ""))
            ann_type = ann.get("announcementTypeName", "")
            print(f"{i:2d}. [{ann_date}] {title}")
            if ann_type:
                print(f"    类型: {ann_type}")
    else:
        print("未找到公告或请求失败")

    # 尝试获取关键公告的详细信息
    if eastmoney_anns:
        print(f"\n" + "=" * 80)
        print("关键公告详细信息")
        print("=" * 80)

        # 查找关键公告
        key_announcements = [
            "国电电力2026年半年度报告",
            "国电电力关于启动收购控股股东部分资产的公告",
            "国电电力2026年半年度报告摘要"
        ]

        for key_title in key_announcements:
            for ann in eastmoney_anns:
                title = ann.get("title", "")
                if key_title in title:
                    print(f"\n【{title}】")
                    print(f"日期: {format_date(ann.get('notice_date', ''))}")
                    art_code = ann.get("art_code", "")
                    if art_code:
                        detail = get_announcement_detail(art_code)
                        if detail:
                            # 尝试获取摘要或关键信息
                            content = detail.get("content", "")
                            if content:
                                # 清理HTML标签并截取前500字符
                                import re
                                clean_content = re.sub(r'<[^>]+>', '', content)
                                clean_content = clean_content.strip()[:500]
                                print(f"摘要: {clean_content}...")
                    break

    print(f"\n" + "=" * 80)
    print("查询完成")

if __name__ == "__main__":
    main()