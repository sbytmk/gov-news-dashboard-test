/* ============================================
   官公庁ニュースダッシュボード
   フロントエンドロジック
   ============================================ */

// ===== キーワード定義（業務影響度の判定に使用） =====
const KEYWORDS = {
  // 業務影響度：高（最重要）- 油脂製造業に直結
  critical: [
    '大豆', '菜種', 'なたね', 'パーム', 'パーム油', 'オリーブ', 'コーン', 'とうもろこし',
    'ごま', 'ゴマ', 'カカオ', 'ひまわり', '油糧', '植物油', '食用油', '油脂',
    '労働災害', '労災', '食品安全', '食品衛生',
  ],
  // 業務影響度：中
  high: [
    '貿易', '輸入', '輸出', '関税', '為替', '円安', '円高', 'ドル',
    '脱炭素', 'カーボン', 'CO2', '温室効果ガス', 'GX',
    'エネルギー', '電力', '燃料', '原油', 'LNG', 'ガス',
    '物価', '原材料', '原料', 'サプライチェーン', '供給',
  ],
  // 業務影響度：中（関連）
  medium: [
    '製造業', '生産', '工場', 'DX', 'AI', 'IoT', 'デジタル',
    '安全', '事故', 'リスク', '規制', '改正',
    '人材', '働き方', '賃金', '最低賃金',
    '物流', '輸送', '港湾',
  ]
};

// ===== 省庁ラベル =====
const SOURCE_LABELS = {
  kantei:  { name: '官邸',     class: 'source-kantei' },
  cao:     { name: '内閣府',   class: 'source-cao' },
  digital: { name: 'デジタル庁', class: 'source-digital' },
  mofa:    { name: '外務省',   class: 'source-mofa' },
  meti:    { name: '経産省',   class: 'source-meti' },
  chusho:  { name: '中企庁',   class: 'source-chusho' },
  jpo:     { name: '特許庁',   class: 'source-jpo' },
  maff:    { name: '農水省',   class: 'source-maff' },
  mof:     { name: '財務省',   class: 'source-mof' },
  fsa:     { name: '金融庁',   class: 'source-fsa' },
  nta:     { name: '国税庁',   class: 'source-nta' },
  jftc:    { name: '公取委',   class: 'source-jftc' },
  soumu:   { name: '総務省',   class: 'source-soumu' },
  mlit:    { name: '国交省',   class: 'source-mlit' },
  mhlw:    { name: '厚労省',   class: 'source-mhlw' },
  env:     { name: '環境省',   class: 'source-env' },
};
// ===== 時計表示 =====
function updateClock() {
  const now = new Date();
  const days = ['日', '月', '火', '水', '木', '金', '土'];
  const dateStr = `${now.getFullYear()}年${(now.getMonth()+1).toString().padStart(2,'0')}月${now.getDate().toString().padStart(2,'0')}日 (${days[now.getDay()]})`;
  const timeStr = `${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}:${now.getSeconds().toString().padStart(2,'0')}`;
  document.getElementById('current-date').textContent = dateStr;
  document.getElementById('current-time').textContent = timeStr;
}
setInterval(updateClock, 1000);
updateClock();

// ===== ニュース業務影響度判定 =====
function evaluateImpact(title) {
  const text = title.toLowerCase();
  const original = title;
  for (const kw of KEYWORDS.critical) {
    if (original.includes(kw)) return { level: 'high', matchedKeyword: kw };
  }
  for (const kw of KEYWORDS.high) {
    if (original.includes(kw)) return { level: 'high', matchedKeyword: kw };
  }
  for (const kw of KEYWORDS.medium) {
    if (original.includes(kw)) return { level: 'medium', matchedKeyword: kw };
  }
  return { level: 'low', matchedKeyword: null };
}

// ===== キーワードハイライト =====
function highlightTitle(title) {
  let result = escapeHtml(title);
  // critical（最重要）を最初に処理
  for (const kw of KEYWORDS.critical) {
    const re = new RegExp(escapeRegExp(kw), 'g');
    result = result.replace(re, `<span class="highlight highlight-critical">${kw}</span>`);
  }
  // high
  for (const kw of KEYWORDS.high) {
    const re = new RegExp(`(?<!<[^>]*)${escapeRegExp(kw)}(?![^<]*>)`, 'g');
    result = result.replace(re, `<span class="highlight">${kw}</span>`);
  }
  return result;
}

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ===== 日付フォーマット =====
function formatDate(isoString) {
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return '';
  const m = (d.getMonth()+1).toString().padStart(2,'0');
  const day = d.getDate().toString().padStart(2,'0');
  const h = d.getHours().toString().padStart(2,'0');
  const min = d.getMinutes().toString().padStart(2,'0');
  return `${m}/${day} ${h}:${min}`;
}

// ===== ニュースアイテムHTML生成 =====
function createNewsItemHTML(item) {
  const source = SOURCE_LABELS[item.source] || { name: item.source, class: '' };
  const impact = evaluateImpact(item.title);
  const titleHighlighted = highlightTitle(item.title);

  const impactBadge = impact.level === 'high'
    ? '<span class="impact-tag impact-high">影響度 高</span>'
    : impact.level === 'medium'
      ? '<span class="impact-tag impact-medium">影響度 中</span>'
      : '';

  return `
    <div class="news-item priority-${impact.level}">
      <div class="news-item-meta">
        <span class="source-tag-inline ${source.class}">${source.name}</span>
        <span class="news-date">${formatDate(item.pubDate)}</span>
        ${impactBadge}
      </div>
      <div class="news-title">${titleHighlighted}</div>
    </div>
  `;
}

// ===== ニュース表示 =====
function renderNews(allNews) {
  // 業務影響度で分類
  const priorityNews = [];
  const recentNews = [];

  allNews.forEach(item => {
    const impact = evaluateImpact(item.title);
    if (impact.level === 'high') {
      priorityNews.push(item);
    } else {
      recentNews.push(item);
    }
  });

  // 日付降順ソート
  priorityNews.sort((a, b) => new Date(b.pubDate) - new Date(a.pubDate));
  recentNews.sort((a, b) => new Date(b.pubDate) - new Date(a.pubDate));

  // 左カラム：注目ニュース（業務影響度：高）
  const priorityContainer = document.getElementById('priority-news');
  document.getElementById('priority-count').textContent = `${priorityNews.length}件`;

  if (priorityNews.length === 0) {
    priorityContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📰</div>
        <div>注目すべきニュースはありません</div>
      </div>`;
  } else {
    // スクロール用に2倍化（ループ表現）
    const html = priorityNews.map(createNewsItemHTML).join('');
    const shouldScroll = priorityNews.length > 5;
    priorityContainer.innerHTML = shouldScroll
      ? `<div class="news-scroll">${html}${html}</div>`
      : html;
  }

  // 右カラム：新着ニュース
  const recentContainer = document.getElementById('recent-news');
  document.getElementById('recent-count').textContent = `${recentNews.length}件`;

  if (recentNews.length === 0) {
    recentContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📭</div>
        <div>新着ニュースはありません</div>
      </div>`;
  } else {
    const html = recentNews.slice(0, 30).map(createNewsItemHTML).join('');
    const shouldScroll = recentNews.length > 6;
    recentContainer.innerHTML = shouldScroll
      ? `<div class="news-scroll">${html}${html}</div>`
      : html;
  }
}

// ===== キーワードティッカー =====
function renderTicker(allNews) {
  // 全ニュースから出現したキーワードを集計
  const kwCount = {};
  const allKeywords = [...KEYWORDS.critical, ...KEYWORDS.high, ...KEYWORDS.medium];

  allNews.forEach(item => {
    allKeywords.forEach(kw => {
      if (item.title.includes(kw)) {
        kwCount[kw] = (kwCount[kw] || 0) + 1;
      }
    });
  });

  // 出現回数順にソート
  const sorted = Object.entries(kwCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15);

  // ティッカーアイテム生成
  let items = '';
  if (sorted.length === 0) {
    // 出現がない場合はデフォルトキーワード表示
    items = ['貿易', '為替', '大豆', '菜種', 'パーム油', '脱炭素', 'エネルギー', '労働災害', '輸入', '食品安全']
      .map(kw => `<div class="ticker-item"><span class="ticker-keyword">${kw}</span>監視中</div>`)
      .join('');
  } else {
    items = sorted
      .map(([kw, count]) => `<div class="ticker-item"><span class="ticker-keyword">${kw}</span>${count}件</div>`)
      .join('');
  }

  // ループのため2倍化
  document.getElementById('keyword-ticker').innerHTML = items + items;
}

// ===== データ読込 =====
async function loadNews() {
  try {
    // キャッシュ回避のためタイムスタンプ付与（更新時刻単位）
    const now = new Date();
    const cacheKey = `${now.getFullYear()}${now.getMonth()}${now.getDate()}${now.getHours() < 12 ? 'AM' : 'PM'}`;
    const response = await fetch(`./data/news.json?v=${cacheKey}`);

    if (!response.ok) throw new Error('データ取得失敗');
    const data = await response.json();

    renderNews(data.items || []);
    renderTicker(data.items || []);

    // 最終更新時刻表示
    if (data.updatedAt) {
      const updated = new Date(data.updatedAt);
      const h = updated.getHours().toString().padStart(2,'0');
      const m = updated.getMinutes().toString().padStart(2,'0');
      const mo = (updated.getMonth()+1).toString().padStart(2,'0');
      const d = updated.getDate().toString().padStart(2,'0');
      document.getElementById('last-updated').textContent = `${mo}/${d} ${h}:${m}`;
    }

    document.getElementById('status-text').textContent = 'SYSTEM ONLINE';
    document.getElementById('status-dot').style.background = 'var(--accent-green)';
  } catch (err) {
    console.error('ニュース読込エラー:', err);
    document.getElementById('status-text').textContent = 'DATA LOAD ERROR';
    document.getElementById('status-dot').style.background = 'var(--accent-red)';

    // フォールバック表示
    document.getElementById('priority-news').innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <div>ニュースデータを読み込めません</div>
        <div style="font-size: 0.9vw; margin-top: 0.5vw; color: var(--text-muted);">次回更新時刻をお待ちください</div>
      </div>`;
  }
}

// ===== 初回読込 =====
loadNews();

// ===== 1分ごとに表示時刻チェック（更新時刻になったら再読込） =====
let lastReloadHour = -1;
setInterval(() => {
  const now = new Date();
  const h = now.getHours();
  const m = now.getMinutes();
  // 6:05 と 12:05 にデータ再読込（GitHub Actionsの実行完了を待つ）
  if ((h === 6 || h === 12) && m === 5 && lastReloadHour !== h) {
    lastReloadHour = h;
    loadNews();
  }
}, 60000);
