#!/usr/bin/env python3
"""
官公庁RSSフィード取得スクリプト
GitHub Actionsで朝6時・昼12時に実行
取得したニュースをdata/news.jsonに保存
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import urllib.request
import xml.etree.ElementTree as ET

# ===== 取得対象RSSフィード =====
# 各省庁の公式RSSフィードURL
RSS_FEEDS = [
    {
        "source": "meti",
        "name": "経済産業省",
        "url": "https://www.meti.go.jp/ml_index_release.rdf",
    },
    {
        "source": "maff",
        "name": "農林水産省",
        "url": "https://www.maff.go.jp/j/rss/press.xml",
    },
    {
        "source": "mlit",
        "name": "国土交通省",
        "url": "https://www.mlit.go.jp/news_rss.xml",
    },
    {
        "source": "mhlw",
        "name": "厚生労働省",
        "url": "https://www.mhlw.go.jp/stf/news.rdf",
    },
    {
        "source": "mof",
        "name": "財務省",
        "url": "https://www.mof.go.jp/rss/release.rdf",
    },
    {
        "source": "env",
        "name": "環境省",
        "url": "https://www.env.go.jp/press/rss.xml",
    },
]

JST = timezone(timedelta(hours=9))

# 名前空間
NS = {
    'rss': 'http://purl.org/rss/1.0/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'atom': 'http://www.w3.org/2005/Atom',
}


def fetch_url(url, timeout=20):
    """URL取得（UAヘッダ付与）"""
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (compatible; GovNewsDashboard/1.0)',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_date(date_str):
    """様々な日付フォーマットをパース"""
    if not date_str:
        return None
    date_str = date_str.strip()

    # RFC822 (Mon, 01 Jan 2024 12:00:00 +0900)
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return dt.astimezone(JST)
    except Exception:
        pass

    # ISO 8601 (2024-01-01T12:00:00+09:00)
    iso_patterns = [
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%Y/%m/%d',
    ]
    for fmt in iso_patterns:
        try:
            dt = datetime.strptime(date_str.replace('Z', '+0000'), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=JST)
            return dt.astimezone(JST)
        except Exception:
            continue

    return None


def parse_feed(xml_bytes, source_id):
    """RSS/RDF/Atomのいずれもパース"""
    items = []
    try:
        # BOM除去
        if xml_bytes.startswith(b'\xef\xbb\xbf'):
            xml_bytes = xml_bytes[3:]
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  ⚠ XMLパースエラー: {e}", file=sys.stderr)
        return items

    # RSS 2.0 (channel/item)
    for item in root.findall('.//channel/item'):
        title_el = item.find('title')
        date_el = item.find('pubDate') or item.find('{http://purl.org/dc/elements/1.1/}date')
        link_el = item.find('link')
        if title_el is not None and title_el.text:
            items.append({
                'title': title_el.text.strip(),
                'pubDate': parse_date(date_el.text if date_el is not None and date_el.text else None),
                'link': link_el.text.strip() if link_el is not None and link_el.text else '',
                'source': source_id,
            })

    # RDF (RSS 1.0) - rss:item 直下
    if not items:
        for item in root.findall('.//{http://purl.org/rss/1.0/}item'):
            title_el = item.find('{http://purl.org/rss/1.0/}title')
            date_el = item.find('{http://purl.org/dc/elements/1.1/}date')
            link_el = item.find('{http://purl.org/rss/1.0/}link')
            if title_el is not None and title_el.text:
                items.append({
                    'title': title_el.text.strip(),
                    'pubDate': parse_date(date_el.text if date_el is not None and date_el.text else None),
                    'link': link_el.text.strip() if link_el is not None and link_el.text else '',
                    'source': source_id,
                })

    # Atom (entry)
    if not items:
        for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
            title_el = entry.find('{http://www.w3.org/2005/Atom}title')
            date_el = entry.find('{http://www.w3.org/2005/Atom}updated') or entry.find('{http://www.w3.org/2005/Atom}published')
            link_el = entry.find('{http://www.w3.org/2005/Atom}link')
            if title_el is not None and title_el.text:
                href = link_el.get('href') if link_el is not None else ''
                items.append({
                    'title': title_el.text.strip(),
                    'pubDate': parse_date(date_el.text if date_el is not None and date_el.text else None),
                    'link': href,
                    'source': source_id,
                })

    return items


def clean_title(title):
    """タイトルクリーンアップ"""
    # 連続空白を1つに
    title = re.sub(r'\s+', ' ', title)
    # 改行コード除去
    title = title.replace('\n', '').replace('\r', '')
    return title.strip()


def main():
    print(f"🚀 官公庁ニュース取得開始 [{datetime.now(JST).isoformat()}]")
    all_items = []

    for feed in RSS_FEEDS:
        print(f"\n📥 {feed['name']} ({feed['url']})")
        try:
            data = fetch_url(feed['url'])
            items = parse_feed(data, feed['source'])
            print(f"  ✓ {len(items)}件取得")
            all_items.extend(items)
        except Exception as e:
            print(f"  ✗ 取得失敗: {e}", file=sys.stderr)
            continue

    # クリーンアップ＆フィルタ
    cleaned = []
    seen_titles = set()
    cutoff = datetime.now(JST) - timedelta(days=14)  # 直近2週間のみ

    for item in all_items:
        title = clean_title(item['title'])
        if not title or len(title) < 5:
            continue
        # 重複除去
        if title in seen_titles:
            continue
        seen_titles.add(title)

        # 日付フィルタ
        pub = item['pubDate']
        if pub is None:
            # 日付不明は除外せず現在時刻として扱う
            pub = datetime.now(JST)
        elif pub < cutoff:
            continue

        cleaned.append({
            'title': title,
            'pubDate': pub.isoformat(),
            'link': item['link'],
            'source': item['source'],
        })

    # 新しい順にソート
    cleaned.sort(key=lambda x: x['pubDate'], reverse=True)

    # 最大120件に制限（表示は分類後30件程度なので余裕を持つ）
    cleaned = cleaned[:120]

    print(f"\n📊 集計結果: {len(cleaned)}件")

    # 保存
    output = {
        'updatedAt': datetime.now(JST).isoformat(),
        'count': len(cleaned),
        'items': cleaned,
    }

    output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'news.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"💾 保存完了: {output_path}")
    print(f"✅ 完了")


if __name__ == '__main__':
    main()
