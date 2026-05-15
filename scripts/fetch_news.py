#!/usr/bin/env python3
"""
官公庁RSSフィード取得スクリプト（v3）
- 農水省・経産省・財務省は全件採用（油脂業と親和性が高い省庁）
- 厚労省・国交省・環境省はキーワードフィルタあり
- 保持期間30日
- 最低表示件数を保証するため補充ロジック追加
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
    {"source": "meti", "name": "経済産業省", "url": "https://www.meti.go.jp/ml_index_release.rdf", "filter": False},
    {"source": "maff", "name": "農林水産省", "url": "https://www.maff.go.jp/j/rss/press.xml",      "filter": False},
    {"source": "mlit", "name": "国土交通省", "url": "https://www.mlit.go.jp/news_rss.xml",         "filter": True},
    {"source": "mhlw", "name": "厚生労働省", "url": "https://www.mhlw.go.jp/stf/news.rdf",         "filter": True},
    {"source": "mof",  "name": "財務省",     "url": "https://www.mof.go.jp/rss/release.rdf",       "filter": False},
    {"source": "env",  "name": "環境省",     "url": "https://www.env.go.jp/press/rss.xml",         "filter": True},
]

JST = timezone(timedelta(hours=9))
KEEP_DAYS = 30
MAX_PER_SOURCE = 15
MIN_TOTAL = 20  # 最低表示件数

NOISE_KEYWORDS = [
    '議事録', '議事次第', '開催案内', '開催のお知らせ', '開催します', '開催結果',
    '開催について', '開催日程', '開催概要', '配布資料', '資料を公表',
    'ワーキンググループ', '審議会', '分科会', '部会', '協議会',
    '採用情報', '採用選考', '募集情報', '募集について', '募集案内',
    '公募', '人事', '幹部名簿', '任命', '内示', '退任',
    '霞が関公募', '係長級', '総合職', '一般職', '技官', '官庁訪問',
    '入札', '落札', '一般競争', '見積', '入札公告',
    '報道発表資料を更新', '報告数の推移を更新', '報道発表資料を掲載',
    'Q&Aを更新', 'よくある質問', '更新しました',
    '月報について', '統計月報', '統計表', '統計データ',
    'WEBマガジン', 'メルマガ', '対象者のみなさまへ', 'ご協力のお願い',
    '幹部紹介', '組織変更', '記者会見', '大臣会見',
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
    '物流', '輸送', '港湾', 'トラック',
    'BCP', '事業継続', '災害対策', '規制改正', '法改正',
]


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
                '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d']:
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
    except ET.ParseError:
        return items

    for item in root.findall('.//channel/item'):
        t = item.find('title')
        d = item.find('pubDate') or item.find('{http://purl.org/dc/elements/1.1/}date')
        l = item.find('link')
        if t is not None and t.text:
            items.append({'title': t.text.strip(), 'pubDate': parse_date(d.text if d is not None else None), 'link': l.text.strip() if l is not None and l.text else '', 'source': source_id})

    if not items:
        for item in root.findall('.//{http://purl.org/rss/1.0/}item'):
            t = item.find('{http://purl.org/rss/1.0/}title')
            d = item.find('{http://purl.org/dc/elements/1.1/}date')
            l = item.find('{http://purl.org/rss/1.0/}link')
            if t is not None and t.text:
                items.append({'title': t.text.strip(), 'pubDate': parse_date(d.text if d is not None else None), 'link': l.text.strip() if l is not None and l.text else '', 'source': source_id})

    if not items:
        for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
            t = entry.find('{http://www.w3.org/2005/Atom}title')
            d = entry.find('{http://www.w3.org/2005/Atom}updated') or entry.find('{http://www.w3.org/2005/Atom}published')
            l = entry.find('{http://www.w3.org/2005/Atom}link')
            if t is not None and t.text:
                items.append({'title': t.text.strip(), 'pubDate': parse_date(d.text if d is not None else None), 'link': l.get('href') if l is not None else '', 'source': source_id})
    return items


def clean_title(title):
    return re.sub(r'\s+', ' ', title).replace('\n', '').replace('\r', '').strip()


def is_noise(title):
    return any(n in title for n in NOISE_KEYWORDS)


def calc_score(title):
    score = 0
    for kw in CRITICAL_KEYWORDS:
        if kw in title: score += 10
    for kw in HIGH_KEYWORDS:
        if kw in title: score += 5
    for kw in MEDIUM_KEYWORDS:
        if kw in title: score += 2
    return score


def main():
    print(f"取得開始 [{datetime.now(JST).isoformat()}]")
    cutoff = datetime.now(JST) - timedelta(days=KEEP_DAYS)

    # 省庁ごとに取得・フィルタ
    by_source = {}
    for feed in RSS_FEEDS:
        print(f"\n{feed['name']} 取得中...")
        try:
            raw = fetch_url(feed['url'])
            items = parse_feed(raw, feed['source'])
            print(f"  {len(items)}件取得")
        except Exception as e:
            print(f"  取得失敗: {e}", file=sys.stderr)
            continue

        seen = set()
        accepted = []
        rejected_noise = []  # ノイズ除外分（補充用に保持）

        for item in items:
            title = clean_title(item['title'])
            if not title or len(title) < 5 or title in seen:
                continue
            seen.add(title)

            pub = item['pubDate'] or datetime.now(JST)
            if isinstance(pub, datetime) and pub < cutoff:
                continue

            pub_iso = pub.isoformat() if isinstance(pub, datetime) else datetime.now(JST).isoformat()
            entry = {'title': title, 'pubDate': pub_iso, 'link': item['link'], 'source': feed['source'], 'score': calc_score(title)}

            if is_noise(title):
                rejected_noise.append(entry)
                continue

            # filter=Trueの省庁はキーワード必須
            if feed['filter'] and entry['score'] == 0:
                rejected_noise.append(entry)
                continue

            accepted.append(entry)

        # スコア降順→日付降順でソートしてMAX_PER_SOURCE件
        accepted.sort(key=lambda x: (-x['score'], x['pubDate']), reverse=False)
        accepted.sort(key=lambda x: x['pubDate'], reverse=True)
        accepted.sort(key=lambda x: -x['score'])
        by_source[feed['source']] = {
            'accepted': accepted[:MAX_PER_SOURCE],
            'rejected': sorted(rejected_noise, key=lambda x: x['pubDate'], reverse=True)
        }

    # 採用分を結合
    final = []
    for src_data in by_source.values():
        final.extend(src_data['accepted'])

    # 最低件数に満たない場合、除外分から補充（日付新しい順）
    if len(final) < MIN_TOTAL:
        print(f"\n件数不足({len(final)}件)のため補充します...")
        all_rejected = []
        for src_data in by_source.values():
            all_rejected.extend(src_data['rejected'])
        all_rejected.sort(key=lambda x: x['pubDate'], reverse=True)

        existing_titles = {i['title'] for i in final}
        for item in all_rejected:
            if len(final) >= MIN_TOTAL:
                break
            if item['title'] not in existing_titles:
                final.append(item)
                existing_titles.add(item['title'])

    # 最終ソート：日付新しい順
    final.sort(key=lambda x: x['pubDate'], reverse=True)

    output_items = [{'title': i['title'], 'pubDate': i['pubDate'], 'link': i['link'], 'source': i['source']} for i in final]

    print(f"\n最終採用: {len(output_items)}件")
    src_count = {}
    for i in output_items:
        src_count[i['source']] = src_count.get(i['source'], 0) + 1
    for src, cnt in src_count.items():
        print(f"  {src}: {cnt}件")

    output = {'updatedAt': datetime.now(JST).isoformat(), 'count': len(output_items), 'items': output_items}
    output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'news.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"保存完了: {output_path}")


if __name__ == '__main__':
    main()
