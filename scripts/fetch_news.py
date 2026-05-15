#!/usr/bin/env python3
"""
官公庁RSSフィード取得スクリプト（改善版 v2）
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import urllib.request
import xml.etree.ElementTree as ET

RSS_FEEDS = [
    {"source": "meti", "name": "経済産業省", "url": "https://www.meti.go.jp/ml_index_release.rdf"},
    {"source": "maff", "name": "農林水産省", "url": "https://www.maff.go.jp/j/rss/press.xml"},
    {"source": "mlit", "name": "国土交通省", "url": "https://www.mlit.go.jp/news_rss.xml"},
    {"source": "mhlw", "name": "厚生労働省", "url": "https://www.mhlw.go.jp/stf/news.rdf"},
    {"source": "mof",  "name": "財務省",     "url": "https://www.mof.go.jp/rss/release.rdf"},
    {"source": "env",  "name": "環境省",     "url": "https://www.env.go.jp/press/rss.xml"},
]

JST = timezone(timedelta(hours=9))

NOISE_KEYWORDS = [
    '議事録', '議事次第', '開催案内', '開催のお知らせ', '開催します', '開催結果',
    '開催について', '開催日程', '開催概要', '配布資料', '資料を公表',
    'ワーキンググループ', '検討会', '審議会', '分科会', '部会', '協議会',
    '採用情報', '採用選考', '募集情報', '募集について', '募集案内',
    '公募', '人事', '幹部名簿', '任命', '内示', '退任',
    '霞が関公募', '係長級', '総合職', '一般職', '技官', '官庁訪問',
    '入札', '落札', '調達', '一般競争', '見積', '入札公告',
    '報道発表資料を更新', '報告数の推移を更新', '報道発表資料を掲載',
    'Q&Aを更新', 'よくある質問', '更新しました',
    '概数', '速報', '月報', '統計月報', '統計表', '統計データ',
    '説明会', 'セミナー', '講演会', '表彰', '受賞', 'WEBマガジン',
    'メルマガ', '対象者のみなさまへ', 'ご協力のお願い',
    '幹部紹介', '組織変更',
]

CRITICAL_KEYWORDS = [
    '大豆', '菜種', 'なたね', 'パーム', 'パーム油', 'オリーブ', 'コーン',
    'とうもろこし', 'ごま', 'カカオ', 'ひまわり', '油糧', '植物油',
    '食用油', '油脂', 'ミール', '搾油',
    '労働災害', '労災', '食品安全', '食品衛生', '食中毒', '異物混入',
    'HACCP', '食品表示',
]

HIGH_KEYWORDS = [
    '貿易', '輸入', '輸出', '関税', '為替', '円安', '円高',
    '脱炭素', 'カーボン', 'CO2', '温室効果ガス', 'GX', 'グリーン',
    'エネルギー', '電力', '燃料', '原油', 'LNG',
    '物価', '原材料', '原料', 'サプライチェーン', '供給',
    '農産物', '食料', '食糧', '飼料', '穀物',
]

MEDIUM_KEYWORDS = [
    '製造業', '工場', '生産性',
    'DX', 'AI', 'IoT', 'デジタル化', 'スマート',
    '労働安全', '労働衛生', '熱中症', '化学物質',
    '最低賃金', '働き方改革', '人手不足',
    '物流', '輸送', '港湾', 'トラック', '2024年問題',
    'BCP', '事業継続', '災害対策',
    '規制改正', '法改正',
]

MAX_PER_SOURCE = 12


def fetch_url(url, timeout=20):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; GovNewsDashboard/1.0)',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_date(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return dt.astimezone(JST)
    except Exception:
        pass
    for fmt in ['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d', '%Y/%m/%d']:
        try:
            dt = datetime.strptime(date_str.replace('Z', '+0000'), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=JST)
            return dt.astimezone(JST)
        except Exception:
            continue
    return None


def parse_feed(xml_bytes, source_id):
    items = []
    try:
        if xml_bytes.startswith(b'\xef\xbb\xbf'):
            xml_bytes = xml_bytes[3:]
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  XMLパースエラー: {e}", file=sys.stderr)
        return items

    for item in root.findall('.//channel/item'):
        title_el = item.find('title')
        date_el = item.find('pubDate') or item.find('{http://purl.org/dc/elements/1.1/}date')
        link_el = item.find('link')
        if title_el is not None and title_el.text:
            items.append({'title': title_el.text.strip(), 'pubDate': parse_date(date_el.text if date_el is not None else None), 'link': link_el.text.strip() if link_el is not None and link_el.text else '', 'source': source_id})

    if not items:
        for item in root.findall('.//{http://purl.org/rss/1.0/}item'):
            title_el = item.find('{http://purl.org/rss/1.0/}title')
            date_el = item.find('{http://purl.org/dc/elements/1.1/}date')
            link_el = item.find('{http://purl.org/rss/1.0/}link')
            if title_el is not None and title_el.text:
                items.append({'title': title_el.text.strip(), 'pubDate': parse_date(date_el.text if date_el is not None else None), 'link': link_el.text.strip() if link_el is not None and link_el.text else '', 'source': source_id})

    if not items:
        for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
            title_el = entry.find('{http://www.w3.org/2005/Atom}title')
            date_el = entry.find('{http://www.w3.org/2005/Atom}updated') or entry.find('{http://www.w3.org/2005/Atom}published')
            link_el = entry.find('{http://www.w3.org/2005/Atom}link')
            if title_el is not None and title_el.text:
                items.append({'title': title_el.text.strip(), 'pubDate': parse_date(date_el.text if date_el is not None else None), 'link': link_el.get('href') if link_el is not None else '', 'source': source_id})

    return items


def clean_title(title):
    title = re.sub(r'\s+', ' ', title)
    return title.replace('\n', '').replace('\r', '').strip()


def is_noise(title):
    for noise in NOISE_KEYWORDS:
        if noise in title:
            return True
    return False


def calc_relevance_score(title):
    score = 0
    for kw in CRITICAL_KEYWORDS:
        if kw in title:
            score += 10
    for kw in HIGH_KEYWORDS:
        if kw in title:
            score += 5
    for kw in MEDIUM_KEYWORDS:
        if kw in title:
            score += 2
    return score


def main():
    print(f"取得開始 [{datetime.now(JST).isoformat()}]")
    all_items = []

    for feed in RSS_FEEDS:
        print(f"\n{feed['name']} 取得中...")
        try:
            data = fetch_url(feed['url'])
            items = parse_feed(data, feed['source'])
            print(f"  {len(items)}件取得")
            all_items.extend(items)
        except Exception as e:
            print(f"  取得失敗: {e}", file=sys.stderr)

    cutoff = datetime.now(JST) - timedelta(days=14)
    candidates = []
    seen_titles = set()

    for item in all_items:
        title = clean_title(item['title'])
        if not title or len(title) < 5:
            continue
        if title in seen_titles:
            continue
        seen_titles.add(title)
        if is_noise(title):
            continue
        score = calc_relevance_score(title)
        if score == 0:
            continue
        pub = item['pubDate']
        if pub is None:
            pub = datetime.now(JST)
        elif pub < cutoff:
            continue
        candidates.append({
            'title': title, 'pubDate': pub.isoformat(),
            'link': item['link'], 'source': item['source'], 'score': score,
        })

    by_source = {}
    for item in candidates:
        by_source.setdefault(item['source'], []).append(item)

    final_items = []
    for source_id, items_list in by_source.items():
        items_list.sort(key=lambda x: (-x['score'], x['pubDate']), reverse=False)
        items_list.sort(key=lambda x: x['pubDate'], reverse=True)
        items_list.sort(key=lambda x: -x['score'])
        final_items.extend(items_list[:MAX_PER_SOURCE])

    final_items.sort(key=lambda x: x['pubDate'], reverse=True)

    output_items = [
        {'title': i['title'], 'pubDate': i['pubDate'], 'link': i['link'], 'source': i['source']}
        for i in final_items
    ]

    print(f"\n最終採用: {len(output_items)}件")

    output = {
        'updatedAt': datetime.now(JST).isoformat(),
        'count': len(output_items),
        'items': output_items,
    }

    output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'news.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"保存完了: {output_path}")


if __name__ == '__main__':
    main()
