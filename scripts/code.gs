/** ====== 設定 ====== */
function cfg() {
  const props = PropertiesService.getScriptProperties();
  return {
    // GitHub設定
    GITHUB_TOKEN: props.getProperty('GITHUB_TOKEN'),
    GITHUB_OWNER: props.getProperty('GITHUB_OWNER'),
    GITHUB_REPO:  props.getProperty('GITHUB_REPO'),
    
    // 既存設定
    UNPAYWALL_EMAIL: props.getProperty('UNPAYWALL_EMAIL'),
    LABELS: JSON.parse(props.getProperty('LABELS_JSON') || '[]'),
    DAYS_LOOKBACK: Number(props.getProperty('DAYS_LOOKBACK') || '7')
  };
}

/** ====== エントリーポイント ====== */
function runHarvest() {
  const C = cfg();
  if (!C.GITHUB_TOKEN || !C.GITHUB_OWNER || !C.GITHUB_REPO) {
    throw new Error('スクリプトプロパティに GITHUB_TOKEN / GITHUB_OWNER / GITHUB_REPO を設定してください');
  }

  const afterQuery = formatAfterQuery(C.DAYS_LOOKBACK);
  let processedCount = 0;

  C.LABELS.forEach(label => {
    // 検索クエリ
    const q = buildQueryForLabel(label, afterQuery);
    // API制限回避のため、1回あたり最大10スレッド程度推奨
    const threads = GmailApp.search(q, 0, 10); 
    Logger.log(`Label: "${label}", Threads: ${threads.length}`);

    threads.forEach(th => {
      const msgs = th.getMessages();
      msgs.forEach(msg => {
        if (!msg.isUnread()) return; // 未読のみ対象

        const html = msg.getBody();
        const raw = msg.getRawContent();
        // 論文情報の抽出
        const entries = extractScholarEntriesRobust(html, raw);
        Logger.log(`Msg: ${msg.getId()}, Entries found: ${entries.length}`);

        entries.forEach(e => {
          processEntry(e, label, C);
          processedCount++;
          // GitHub APIのレート制限考慮
          Utilities.sleep(1500);
        });

        // 処理が終わったら既読にする
        if (entries.length > 0) {
          msg.markRead();
        }
      });
    });
  });

  Logger.log(`Total processed entries: ${processedCount}`);
}

/** ====== 個別の論文を処理 ====== */
function processEntry(e, label, C) {
  // URLなどの正規化・メタデータ取得
  const finalUrl = expandScholarRedirect(e.url);
  const normUrl = normalizeUrl(finalUrl || e.url);
  const meta = resolveMetadata({ title: e.title, url: finalUrl || e.url });
  
  // OAステータス確認
  const oa = meta.doi ? unpaywallLookup(meta.doi, C.UNPAYWALL_EMAIL) : guessOpenFromUrl(finalUrl);
  
  // 重複チェック用キーの生成
  const dupKey = buildDupKey(meta.doi, meta.arxiv, normUrl);
  if (!dupKey) {
    Logger.log(`Skipping (No Key): ${e.title}`);
    return;
  }

  // GitHub上での重複チェック
  if (existsInGitHub(C, dupKey)) {
    Logger.log(`Duplicate found in GitHub: ${dupKey}`);
    return;
  }

  // === ラベル生成ロジック ===
  // label(検索語句)を含める
  const issueLabels = [label]; 
  
  // yearがあれば追加
  if (meta.year) {
    issueLabels.push(String(meta.year));
  }
  
  // oa_statusがあれば追加 (例: gold, green, bronze, closed)
  const status = (oa && oa.oa_status) ? oa.oa_status : 'closed';
  issueLabels.push(status);

  // 日本語タイトルの生成
  const titleJa = translateJa(e.title);

  // Issue本文の作成
  const body = createIssueBody(e, meta, oa, dupKey, label, normUrl, status);
  
  // Issueの作成
  createGitHubIssue(C, {
    title: titleJa || e.title, // 日本語タイトル（失敗時は英語）
    body: body,
    labels: issueLabels
  });
}

/** ====== Markdown本文の生成 ====== */
function createIssueBody(entry, meta, oa, dupKey, label, normUrl, status) {
  const snipJa = translateJa(entry.snippet); 
  const oaUrl = (oa && oa.oa_url) ? oa.oa_url : 'N/A';
  const authors = meta.authors || entry.authorLine || 'N/A';
  const venue = meta.venue || 'N/A';
  const year = meta.year || 'N/A';

  return `
## ${entry.title}
- **Authors:** ${authors}
- **Venue:** ${venue}
- **Year:** ${year}
- **OA Status:** ${status}
- **Label:** ${label}
- **Source URL:** ${normUrl}
- **OA URL:** ${oaUrl}

## 概要
${snipJa}

> ${entry.snippet}

---
`;
}

/** ====== GitHub API: Issue検索（重複チェック） ====== */
function existsInGitHub(config, uniqueKey) {
  try {
    const q = `repo:${config.GITHUB_OWNER}/${config.GITHUB_REPO} "${uniqueKey}" is:issue`;
    const url = `https://api.github.com/search/issues?q=${encodeURIComponent(q)}`;
    
    const res = UrlFetchApp.fetch(url, {
      method: 'get',
      headers: { 
        'Authorization': `Bearer ${config.GITHUB_TOKEN}`,
        'Accept': 'application/vnd.github.v3+json'
      },
      muteHttpExceptions: true
    });
    
    if (res.getResponseCode() !== 200) {
      Logger.log(`GitHub Search Error: ${res.getResponseCode()} ${res.getContentText()}`);
      // 検索エラー時は安全側に倒して重複なし(false)とみなして作成に進むか、
      // 厳密にするなら true を返してスキップさせるか。ここでは重複なしとして進める。
      return false; 
    }
    
    const json = JSON.parse(res.getContentText());
    return json.total_count > 0;
  } catch (e) {
    Logger.log(`Error in existsInGitHub: ${e}`);
    return false;
  }
}

/** ====== GitHub API: Issue作成 ====== */
function createGitHubIssue(config, payload) {
  const url = `https://api.github.com/repos/${config.GITHUB_OWNER}/${config.GITHUB_REPO}/issues`;
  
  try {
    const res = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: { 
        'Authorization': `Bearer ${config.GITHUB_TOKEN}`,
        'Accept': 'application/vnd.github.v3+json'
      },
      payload: JSON.stringify(payload)
    });
    Logger.log(`Created Issue: ${payload.title}`);
  } catch (e) {
    Logger.log(`Error creating issue: ${e}`);
  }
}

/** ====== 以下、ヘルパー関数群 ====== */
function formatAfterQuery(daysBack) {
  const d = new Date();
  d.setDate(d.getDate() - daysBack);
  return `after:${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
}
function buildQueryForLabel(label, afterQuery) {
  return `label:"${String(label).replace(/"/g, '\\"')}" ${afterQuery}`.trim();
}
function extractScholarEntriesRobust(htmlFromBody, rawContent) {
  let entries = extractFromHtml(htmlFromBody);
  if (entries.length > 0) return entries;
  const html = extractHtmlFromRaw(rawContent);
  return html ? extractFromHtml(html) : [];
}
function extractFromHtml(html) {
  const entries = [];
  const reA = /<a[^>]*href=("|')([^"']+scholar_url[^"']+)\1[^>]*>([\s\S]*?)<\/a>/gi;
  let m;
  const seen = new Set();
  while ((m = reA.exec(html)) !== null) {
    const href = m[2];
    const titleRaw = stripTags(decodeHtml(m[3])).replace(/\s+/g,' ').trim();
    if (!titleRaw) continue;
    const finalUrl = expandScholarRedirect(href) || href;
    const key = `${titleRaw}||${finalUrl}`;
    if (seen.has(key)) continue;
    seen.add(key);
    let snippet = '';
    const tail = html.slice(m.index, m.index + 2000);
    const snip1 = tail.match(/<div[^>]*class=("|')gse_alrt_sni\1[^>]*>([\s\S]*?)<\/div>/i);
    if (snip1) snippet = stripTags(decodeHtml(snip1[2])).replace(/\s+/g,' ').trim();
    else {
      const snip2 = tail.match(/<\/a>\s*<\/h3>\s*<div[^>]*>([\s\S]{40,600}?)(?:<\/div>|<br|<table|<h3)/i);
      if (snip2) snippet = stripTags(decodeHtml(snip2[1])).replace(/\s+/g,' ').trim();
    }
    entries.push({ title: titleRaw, url: finalUrl, authorLine: '', snippet: snippet });
  }
  // Fallback
  if (entries.length === 0) {
    const reDirect = /<a[^>]*href=("|')([^"']+?(?:arxiv\.org\/(?:pdf|abs)\/\d{4}\.\d{4,5}|doi\.org\/10\.\d{4,9}\/[^"']+))\1[^>]*>([\s\S]*?)<\/a>/gi;
    while ((m = reDirect.exec(html)) !== null) {
      const href = decodeHtml(m[2]);
      const titleRaw = stripTags(decodeHtml(m[3])).replace(/\s+/g,' ').trim();
      if (!titleRaw) continue;
      if (!seen.has(`${titleRaw}||${href}`)) {
        seen.add(`${titleRaw}||${href}`);
        entries.push({ title: titleRaw, url: href, authorLine: '', snippet: '' });
      }
    }
  }
  return entries;
}
function extractHtmlFromRaw(raw) {
  if (!raw) return '';
  const qp = raw.includes('Content-Transfer-Encoding: quoted-printable');
  if (qp) {
    const start = raw.search(/<!doctype html|<html/i);
    if (start >= 0) return qpDecode(raw.slice(start));
  }
  const start2 = raw.search(/<!doctype html|<html/i);
  return start2 >= 0 ? raw.slice(start2) : '';
}
function qpDecode(s) {
  s = s.replace(/=\r?\n/g, '');
  return s.replace(/=([A-Fa-f0-9]{2})/g, (_, hex) => {
    try { return String.fromCharCode(parseInt(hex, 16)); } catch (e) { return _; }
  });
}
function expandScholarRedirect(u) {
  try {
    const q = (u.split('?')[1] || '');
    const params = Object.fromEntries(q.split('&').map(kv => kv.split('=').map(decodeURIComponent)).filter(a => a.length === 2));
    if (params.url) return decodeURIComponent(params.url);
    return u;
  } catch (e) { return u; }
}
function normalizeUrl(u) {
  if (!u) return '';
  try {
    const url = new URL(u);
    ['utm_source','utm_medium','utm_campaign','utm_term','utm_content','gclid','fbclid','ref'].forEach(k => url.searchParams.delete(k));
    return `${url.protocol}//${url.host}${url.pathname}${url.search}`;
  } catch (e) { return u; }
}
function resolveMetadata(seed) {
  const out = { doi: '', arxiv: '', authors: '', year: '', venue: '' };
  if (seed.url) {
    const mDoi = seed.url.match(/10\.\d{4,9}\/[^\s#?"]+/i);
    if (mDoi) out.doi = mDoi[0].replace(/[\.,]$/, '');
    const mArxiv = seed.url.match(/arxiv\.org\/(?:abs|pdf)\/(\d{4}\.\d{4,5})(?:v\d+)?/i);
    if (mArxiv) out.arxiv = mArxiv[1];
  }
  if (!out.doi && seed.title) {
    const cr = crossrefByTitle(seed.title);
    if (cr && cr.DOI) {
      out.doi = cr.DOI;
      out.authors = extractAuthors(cr.author);
      out.year = (cr.issued?.['date-parts']?.[0]?.[0]) || '';
      out.venue = cr['container-title'] ? (Array.isArray(cr['container-title']) ? cr['container-title'][0] : cr['container-title']) : '';
    }
  }
  return out;
}
function extractAuthors(arr) {
  if (!arr || !arr.length) return '';
  return arr.map(a => [a.given, a.family].filter(Boolean).join(' ')).join(', ');
}
function crossrefByTitle(title) {
  try {
    const url = 'https://api.crossref.org/works?query.title=' + encodeURIComponent(title) + '&rows=1&select=DOI,title,author,issued,container-title';
    const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    const json = JSON.parse(res.getContentText());
    return json?.message?.items?.[0] || null;
  } catch (e) { return null; }
}
function unpaywallLookup(doi, email) {
  try {
    const url = 'https://api.unpaywall.org/v2/' + encodeURIComponent(doi) + '?email=' + encodeURIComponent(email);
    const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    if (res.getResponseCode() !== 200) return null;
    const j = JSON.parse(res.getContentText());
    const best = j.best_oa_location || {};
    return { is_oa: !!j.is_oa, oa_status: j.oa_status || '', oa_url: best.url_for_pdf || best.url || '' };
  } catch (e) { return null; }
}
function guessOpenFromUrl(u) {
  if (!u) return null;
  if (/arxiv\.org$/i.test(new URL(u).host)) return { is_oa: true, oa_status: 'green', oa_url: u };
  return null;
}
function translateJa(text) {
  if (!text) return '';
  try { return LanguageApp.translate(text, 'en', 'ja'); } catch (e) { return text; }
}
function stripTags(s) { return s.replace(/<[^>]*>/g, ''); }
function decodeHtml(s) {
  const map = { '&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&#39;':"'" };
  return s.replace(/(&amp;|&lt;|&gt;|&quot;|&#39;)/g, m => map[m] || m);
}
function buildDupKey(doi, arxiv, urlNorm) {
  if (doi) return `doi:${doi.toLowerCase()}`;
  if (arxiv) return `arxiv:${arxiv.toLowerCase()}`;
  if (urlNorm) return `url:${urlNorm.toLowerCase()}`;
  return '';
}