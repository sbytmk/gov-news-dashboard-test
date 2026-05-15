#!/usr/bin/env python3
"""
官公庁RSSフィード取得スクリプト（v4）
- 情報源拡充: 首相官邸/デジタル庁/内閣府/公取委/中企庁 追加
- キーワード拡充: AI/生成AI/地政学/サイバー/半導体 等
- 補充ロジック改善: 完全無関係なノイズは補充対象外
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
    # 官邸・内閣系（最重要・無条件採用）
    {"source": "kantei",  "name": "首相官邸",     "url": "https://www.kantei.go.jp/index.rdf",          "filter": False},
    {"source": "cao",     "name": "内閣府",       "url": "https://www.cao.go.jp/news.rdf",              "filter": False},
    {"source": "digital", "name": "デジタル庁",   "url": "https://www.digital.go.jp/rss/posts",         "filter": False},
    # 経済・産業系
    {"source": "meti",    "name": "経済産業省",   "url": "https://www.meti.go.jp/ml_index_release.rdf", "filter": False},
    {"source": "maff",    "name": "農林水産省",   "url": "https://www.maff.go.jp/j/rss/press.xml",      "filter": False},
    {"source": "mof",     "name": "財務省",       "url": "https://www.mof.go.jp/rss/release.rdf",       "filter": False},
    {"source": "jftc",    "name": "公正取引委員会","url": "https://www.jftc.go.jp/houdou/index.rdf",     "filter": False},
    # キーワードフィルタあり（情報量が多すぎる省庁）
    {"source": "mlit",    "name": "国土交通省",   "url": "https://www.mlit.go.jp/news_rss.xml",         "filter": True},
    {"source": "mhlw",    "name": "厚生労働省",   "url": "https://www.mhlw.go.jp/stf/news.rdf",         "filter": True},
    {"source": "env",     "name": "環境省",       "url": "https://www.env.go.jp/press/rss.xml",         "filter": True},
]

JST = timezone(timedelta(hours=9))
KEEP_DAYS = 30
MAX_PER_SOURCE = 12
MIN_TOTAL = 25

# ノイズ：管理業務的な定例情報
NOISE_KEYWORDS = [
    '議事録', '議事次第', '配布資料',
    '採用情報', '採用選考', '募集情報', '募集について', '募集案内',
    '霞が関公募', '係長級', '総合職', '一般職', '技官', '官庁訪問',
    '入札', '落札', '一般競争', '見積', '入札公告',
    '報道発表資料を更新', '報告数の推移を更新', '報道発表資料を掲載',
    'Q&Aを更新', 'よくある質問',
    'WEBマガジン', 'メルマガ', '対象者のみなさまへ', 'ご協力のお願い',
    '幹部紹介', '幹部名簿', '組織変更',
    '21世紀出生児', '人口動態統計', 'ハンセン病', '抑留者',
    '医療用手袋', '化粧品・医薬部外品', '再生医療等製品',
    'キャリアコンサルタント', '医療職', '医療安全のためのピアレビュー',
    'プログラム医療機器', '医療上の必要性',
]

# 油脂業に直結
CRITICAL_KEYWORDS = [
    '大豆', '菜種', 'なたね', 'パーム', 'パーム油', 'オリーブ', 'コーン',
    'とうもろこし', 'ごま', 'カカオ', 'ひまわり', '油糧', '植物油',
    '食用油', '油脂', 'ミール', '搾油',
    '労働災害', '労災', '食品安全', '食品衛生', '食中毒', '異物混入',
    'HACCP', '食品表示',
]

# 重要：地政学・経済・エネルギー・AI
HIGH_KEYWORDS = [
    # 貿易・通商
    '貿易', '輸入', '輸出', '関税', '通商', '経済連携', 'TPP', 'FTA',
    # 為替・経済
    '為替', '円安', '円高', '物価', 'インフレ',
    # 地政学
    'ウクライナ', 'ロシア', '中東', 'イラン', 'イスラエル', 'ガザ',
    '紅海', 'ホルムズ', '台湾', '米中', '韓国', '北朝鮮',
    # エネルギー
    '脱炭素', 'カーボン', 'CO2', '温室効果ガス', 'GX', 'グリーン',
    'エネルギー', '電力', '燃料', '原油', 'LNG', '水素', '再エネ',
    # 産業
    '半導体', 'レアアース', '戦略物資', 'サプライチェーン', '原材料', '原料',
    '農産物', '食料', '食糧', '飼料', '穀物',
    # AI・DX
    'AI', '人工知能', '生成AI', 'ChatGPT', 'LLM', 'ディープラーニング',
    'DX', 'デジタル', 'デジタル化',
    # サイバー
    'サイバー', 'サイバーセキュリティ', 'ランサム', '不正アクセス',
    # 感染症
    '感染症', 'パンデミック', '新型コロナ', 'インフルエンザ', 'ハンタウイルス',
    '鳥インフルエンザ', 'バイオテロ',
]

MEDIUM_KEYWORDS = [
    '製造業', '工場', '生産性', 'IoT', 'スマート', 'ロボット',
    '労働安全', '労働衛生', '熱中症', '化学物質',
    '最低賃金', '働き方改革', '人手不足', '人材育成',
    '物流', '輸送', '港湾', 'トラック',
    'BCP', '事業継続', '災害対策',
    '規制改正', '法改正', '補助金', '支援策',
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
        rejected_with_score = []  # スコア>0 だが filter で落ちたもの（補充候補）

        for item in items:
            title = clean_title(item['title'])
            if not title or len(title) < 5 or title in seen:
                continue
            seen.add(title)

            pub = item['pubDate'] or datetime.now(JST)
            if isinstance(pub, datetime) and pub < cutoff:
                continue

            pub_iso = pub.isoformat() if isinstance(pub, datetime) else datetime.now(JST).isoformat()
            score = calc_score(title)
            entry = {'title': title, 'pubDate': pub_iso, 'link': item['link'], 'source': feed['source'], 'score': score}

            # ノイズは完全除外
            if is_noise(title):
                continue

            # filter=Trueの省庁はキーワード必須
            if feed['filter'] and score == 0:
                continue

            accepted.append(entry)

        # スコア降順→日付降順
        accepted.sort(key=lambda x: (-x['score'], x['pubDate'][::-1] if False else x['pubDate']), reverse=False)
        accepted.sort(key=lambda x: x['pubDate'], reverse=True)
        accepted.sort(key=lambda x: -x['score'])
        by_source[feed['source']] = accepted[:MAX_PER_SOURCE]

    # 採用分を結合
    final = []
    for items_list in by_source.values():
        final.extend(items_list)

    # 最終ソート：日付新しい順
    final.sort(key=lambda x: x['pubDate'], reverse=True)

    output_items = [{'title': i['title'], 'pubDate': i['pubDate'], 'link': i['link'], 'source': i['source']} for i in final]

    print(f"\n最終採用: {len(output_items)}件")
    src_count = {}
    for i in output_items:
        src_count[i['source']] = src_count.get(i['source'], 0) + 1
    for src, cnt in sorted(src_count.items()):
        print(f"  {src}: {cnt}件")

    output = {'updatedAt': datetime.now(JST).isoformat(), 'count': len(output_items), 'items': output_items}
    output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'news.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"保存完了: {output_path}")


if __name__ == '__main__':
    main()
