function cfg() {
  const props = PropertiesService.getScriptProperties();
  return {
    NOTION_TOKEN: props.getProperty('NOTION_TOKEN'),
    NOTION_DATABASE_ID:
      props.getProperty('NOTION_PAPER_DATABASE_ID') ||
      props.getProperty('NOTION_DATABASE_ID'),
    NOTION_VERSION: props.getProperty('NOTION_VERSION') || '2022-06-28',
    UNPAYWALL_EMAIL: props.getProperty('UNPAYWALL_EMAIL'),
    LABELS: JSON.parse(props.getProperty('LABELS_JSON') || '[]'),
    DAYS_LOOKBACK: Number(props.getProperty('DAYS_LOOKBACK') || '7'),
    DRY_RUN: String(props.getProperty('DRY_RUN') || '').toLowerCase() === 'true'
  };
}

function runHarvest() {
  const C = cfg();
  if (!C.NOTION_TOKEN || !C.NOTION_DATABASE_ID) {
    throw new Error('Set NOTION_TOKEN and NOTION_PAPER_DATABASE_ID in Script Properties.');
  }
  if (!C.LABELS.length) {
    throw new Error('Set LABELS_JSON in Script Properties, for example ["google-scholar"].');
  }

  const afterQuery = formatAfterQuery(C.DAYS_LOOKBACK);
  let processedCount = 0;
  let failedMessages = 0;

  C.LABELS.forEach(label => {
    const q = buildQueryForLabel(label, afterQuery);
    const threads = GmailApp.search(q, 0, 10);
    Logger.log(`Label: "${label}", Threads: ${threads.length}`);

    threads.forEach(thread => {
      thread.getMessages().forEach(msg => {
        if (!msg.isUnread()) return;

        const entries = extractScholarEntriesRobust(msg.getBody(), msg.getRawContent());
        Logger.log(`Msg: ${msg.getId()}, Entries found: ${entries.length}`);
        if (entries.length === 0) return;

        let messageSucceeded = true;
        entries.forEach(entry => {
          try {
            const result = processEntry(entry, label, C);
            if (result && result.processed) processedCount++;
          } catch (err) {
            messageSucceeded = false;
            Logger.log(`Failed entry "${entry.title}": ${err && err.stack ? err.stack : err}`);
          }
          Utilities.sleep(1000);
        });

        if (messageSucceeded && !C.DRY_RUN) {
          msg.markRead();
        } else if (!messageSucceeded) {
          failedMessages++;
          Logger.log(`Leaving unread for retry: ${msg.getId()}`);
        } else {
          Logger.log(`DRY_RUN enabled; leaving unread: ${msg.getId()}`);
        }
      });
    });
  });

  Logger.log(`Total processed entries: ${processedCount}, failed messages: ${failedMessages}`);
}

function processEntry(entry, label, C) {
  const finalUrl = expandScholarRedirect(entry.url);
  const sourceUrl = normalizeUrl(finalUrl || entry.url);
  const meta = resolveMetadata({ title: entry.title, url: finalUrl || entry.url });
  const oa = meta.doi ? unpaywallLookup(meta.doi, C.UNPAYWALL_EMAIL) : guessOpenFromUrl(sourceUrl);
  const paperKey = buildPaperKey(meta.doi, meta.arxiv, sourceUrl);

  if (!paperKey) {
    Logger.log(`Skipping without stable key: ${entry.title}`);
    return { processed: false, action: 'skipped_without_key' };
  }

  if (existsInNotion(C, meta, sourceUrl, paperKey)) {
    Logger.log(`Duplicate found in Notion: ${paperKey}`);
    return { processed: false, action: 'duplicate' };
  }

  const properties = createPaperProperties(entry, meta, oa, paperKey, label, sourceUrl, C);
  if (C.DRY_RUN) {
    Logger.log(`DRY_RUN would create Notion paper card: ${entry.title} (${paperKey})`);
    return { processed: true, action: 'dry_run' };
  }

  const page = createNotionPage(C, properties);
  Logger.log(`Created Notion paper card: ${entry.title} (${page.id})`);
  return { processed: true, action: 'created', pageId: page.id };
}

function createPaperProperties(entry, meta, oa, paperKey, label, sourceUrl, C) {
  const oaStatus = normalizeOaStatus((oa && oa.oa_status) || 'closed');
  const titleJa = translateJa(entry.title);
  const summaryJa = translateJa(entry.snippet);
  const pdfUrl = pdfUrlFrom(sourceUrl, oa && oa.oa_url);
  const tags = [label, 'google-scholar'];
  if (meta.year) tags.push(String(meta.year));
  if (oaStatus) tags.push(oaStatus);

  const properties = {
    Title: titleValue(titleJa || entry.title),
    Status: statusValue(C, 'Inbox'),
    'Paper Key': richText(paperKey),
    Authors: richText(meta.authors || entry.authorLine || ''),
    Venue: richText(meta.venue || ''),
    Source: richText('gmail-google-scholar'),
    'Source URL': urlValue(sourceUrl),
    'PDF URL': urlValue(pdfUrl),
    'Short Summary JA': richText(summaryJa || ''),
    Reason: richText(`Imported from Gmail Google Scholar alert: ${label}`),
    Tags: multiSelect(tags),
    'OA Status': selectValue(oaStatus || 'unknown')
  };

  if (meta.year) properties.Year = numberValue(Number(meta.year));
  if (meta.doi) properties.DOI = richText(meta.doi);
  if (meta.arxiv) properties['arXiv ID'] = richText(meta.arxiv);
  return properties;
}

function existsInNotion(C, meta, sourceUrl, paperKey) {
  const filters = [];
  if (meta.doi) filters.push({ property: 'DOI', rich_text: { equals: meta.doi } });
  if (meta.doi && meta.doi.toLowerCase() !== meta.doi) {
    filters.push({ property: 'DOI', rich_text: { equals: meta.doi.toLowerCase() } });
  }
  if (meta.arxiv) filters.push({ property: 'arXiv ID', rich_text: { equals: meta.arxiv } });
  if (meta.arxiv && meta.arxiv.toLowerCase() !== meta.arxiv) {
    filters.push({ property: 'arXiv ID', rich_text: { equals: meta.arxiv.toLowerCase() } });
  }
  if (sourceUrl) filters.push({ property: 'Source URL', url: { equals: sourceUrl } });
  if (paperKey) filters.push({ property: 'Paper Key', rich_text: { equals: paperKey } });
  if (filters.length === 0) return false;

  const payload = {
    page_size: 1,
    filter: filters.length === 1 ? filters[0] : { or: filters }
  };
  const data = notionRequest(C, 'post', `/databases/${C.NOTION_DATABASE_ID}/query`, payload);
  return (data.results || []).length > 0;
}

function createNotionPage(C, properties) {
  return notionRequest(C, 'post', '/pages', {
    parent: { database_id: C.NOTION_DATABASE_ID },
    properties: properties
  });
}

function notionRequest(C, method, path, payload) {
  const options = {
    method: method,
    contentType: 'application/json',
    headers: {
      Authorization: `Bearer ${C.NOTION_TOKEN}`,
      'Notion-Version': C.NOTION_VERSION
    },
    muteHttpExceptions: true
  };
  if (payload) options.payload = JSON.stringify(payload);

  const res = UrlFetchApp.fetch(`https://api.notion.com/v1${path}`, options);
  const status = res.getResponseCode();
  const text = res.getContentText();
  const data = text ? JSON.parse(text) : {};
  if (status < 200 || status >= 300) {
    throw new Error(`Notion API error ${status}: ${text}`);
  }
  return data;
}

function databasePropertyType(C, name) {
  if (!C._databaseSchema) {
    C._databaseSchema = notionRequest(C, 'get', `/databases/${C.NOTION_DATABASE_ID}`);
  }
  const prop = C._databaseSchema.properties && C._databaseSchema.properties[name];
  return prop ? prop.type : '';
}

function statusValue(C, name) {
  return databasePropertyType(C, 'Status') === 'status'
    ? { status: { name: name } }
    : selectValue(name);
}

function titleValue(value) {
  return { title: [{ type: 'text', text: { content: truncateText(value || '', 2000) } }] };
}

function richText(value) {
  const text = truncateText(value || '', 2000);
  return text ? { rich_text: [{ type: 'text', text: { content: text } }] } : { rich_text: [] };
}

function urlValue(value) {
  return { url: value || null };
}

function selectValue(value) {
  return { select: { name: value || 'unknown' } };
}

function numberValue(value) {
  return { number: Number.isFinite(value) ? value : null };
}

function multiSelect(values) {
  const seen = {};
  const names = values
    .map(v => String(v || '').trim())
    .filter(Boolean)
    .filter(v => {
      const key = v.toLowerCase();
      if (seen[key]) return false;
      seen[key] = true;
      return true;
    })
    .slice(0, 20);
  return { multi_select: names.map(name => ({ name: truncateText(name, 100) })) };
}

function truncateText(value, maxLength) {
  const text = String(value || '');
  return text.length > maxLength ? text.slice(0, maxLength) : text;
}

function formatAfterQuery(daysBack) {
  const d = new Date();
  d.setDate(d.getDate() - daysBack);
  return `after:${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
}

function buildQueryForLabel(label, afterQuery) {
  return `label:"${String(label).replace(/"/g, '\\"')}" ${afterQuery}`.trim();
}

function extractScholarEntriesRobust(htmlFromBody, rawContent) {
  const entries = extractFromHtml(htmlFromBody);
  if (entries.length > 0) return entries;
  const html = extractHtmlFromRaw(rawContent);
  return html ? extractFromHtml(html) : [];
}

function extractFromHtml(html) {
  const entries = [];
  const reA = /<a[^>]*href=("|')([^"']+scholar_url[^"']+)\1[^>]*>([\s\S]*?)<\/a>/gi;
  let m;
  const seen = {};

  while ((m = reA.exec(html)) !== null) {
    const href = m[2];
    const titleRaw = stripTags(decodeHtml(m[3])).replace(/\s+/g, ' ').trim();
    if (!titleRaw) continue;
    const finalUrl = expandScholarRedirect(href) || href;
    const key = `${titleRaw}||${finalUrl}`;
    if (seen[key]) continue;
    seen[key] = true;
    entries.push({
      title: titleRaw,
      url: finalUrl,
      authorLine: '',
      snippet: snippetNear(html, m.index)
    });
  }

  if (entries.length === 0) {
    const reDirect = /<a[^>]*href=("|')([^"']+?(?:arxiv\.org\/(?:pdf|abs)\/[^"']+|doi\.org\/10\.\d{4,9}\/[^"']+))\1[^>]*>([\s\S]*?)<\/a>/gi;
    while ((m = reDirect.exec(html)) !== null) {
      const href = decodeHtml(m[2]);
      const titleRaw = stripTags(decodeHtml(m[3])).replace(/\s+/g, ' ').trim();
      if (!titleRaw) continue;
      const key = `${titleRaw}||${href}`;
      if (seen[key]) continue;
      seen[key] = true;
      entries.push({ title: titleRaw, url: href, authorLine: '', snippet: snippetNear(html, m.index) });
    }
  }
  return entries;
}

function snippetNear(html, index) {
  const tail = html.slice(index, index + 2000);
  const snip1 = tail.match(/<div[^>]*class=("|')gse_alrt_sni\1[^>]*>([\s\S]*?)<\/div>/i);
  if (snip1) return stripTags(decodeHtml(snip1[2])).replace(/\s+/g, ' ').trim();
  const snip2 = tail.match(/<\/a>\s*<\/h3>\s*<div[^>]*>([\s\S]{40,600}?)(?:<\/div>|<br|<table|<h3)/i);
  return snip2 ? stripTags(decodeHtml(snip2[1])).replace(/\s+/g, ' ').trim() : '';
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
    try {
      return String.fromCharCode(parseInt(hex, 16));
    } catch (e) {
      return _;
    }
  });
}

function expandScholarRedirect(u) {
  if (!u) return '';
  try {
    const url = new URL(u);
    return url.searchParams.get('url') || u;
  } catch (e) {
    try {
      const query = String(u).split('?')[1] || '';
      const pairs = query.split('&').map(kv => kv.split('=').map(decodeURIComponent));
      for (let i = 0; i < pairs.length; i++) {
        if (pairs[i][0] === 'url') return pairs[i][1];
      }
    } catch (ignored) {}
    return u;
  }
}

function normalizeUrl(u) {
  if (!u) return '';
  try {
    const url = new URL(u);
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid', 'ref'].forEach(k => {
      url.searchParams.delete(k);
    });
    url.hash = '';
    const sortedParams = Array.from(url.searchParams.entries()).sort((a, b) => {
      const keyCompare = a[0].localeCompare(b[0]);
      return keyCompare || a[1].localeCompare(b[1]);
    });
    const query = sortedParams.length
      ? '?' + sortedParams.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&')
      : '';
    const pathname = url.pathname !== '/' && url.pathname.endsWith('/') ? url.pathname.slice(0, -1) : url.pathname;
    return `${url.protocol.toLowerCase()}//${url.host.toLowerCase()}${pathname}${query}`;
  } catch (e) {
    return u;
  }
}

function resolveMetadata(seed) {
  const out = { doi: '', arxiv: '', authors: '', year: '', venue: '' };
  if (seed.url) {
    out.doi = extractDoi(seed.url);
    out.arxiv = extractArxiv(seed.url);
  }
  if (!out.doi && seed.title) {
    const cr = crossrefByTitle(seed.title);
    if (cr && cr.DOI) {
      out.doi = cr.DOI;
      out.authors = extractAuthors(cr.author);
      out.year = (cr.issued && cr.issued['date-parts'] && cr.issued['date-parts'][0] && cr.issued['date-parts'][0][0]) || '';
      out.venue = cr['container-title'] ? (Array.isArray(cr['container-title']) ? cr['container-title'][0] : cr['container-title']) : '';
    }
  }
  return out;
}

function extractDoi(value) {
  const match = String(value || '').match(/10\.\d{4,9}\/[^\s#?<>"]+/i);
  return match ? trimIdentifier(match[0]) : '';
}

function extractArxiv(value) {
  const text = String(value || '');
  const fromUrl = text.match(/arxiv\.org\/(?:abs|pdf)\/([A-Za-z.-]+\/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?/i);
  if (fromUrl) return fromUrl[1];
  const explicit = text.match(/\barXiv:\s*([A-Za-z.-]+\/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?\b/i);
  return explicit ? explicit[1] : '';
}

function trimIdentifier(value) {
  let out = String(value || '').trim();
  while (/[.,;:]$/.test(out)) out = out.slice(0, -1);
  while (out.endsWith(')') && countChar(out, '(') < countChar(out, ')')) out = out.slice(0, -1);
  return out;
}

function countChar(value, char) {
  return (String(value).match(new RegExp(`\\${char}`, 'g')) || []).length;
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
    return json && json.message && json.message.items ? json.message.items[0] : null;
  } catch (e) {
    Logger.log(`Crossref lookup failed: ${e}`);
    return null;
  }
}

function unpaywallLookup(doi, email) {
  if (!doi || !email) return null;
  try {
    const url = 'https://api.unpaywall.org/v2/' + encodeURIComponent(doi) + '?email=' + encodeURIComponent(email);
    const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    if (res.getResponseCode() !== 200) return null;
    const j = JSON.parse(res.getContentText());
    const best = j.best_oa_location || {};
    return { is_oa: !!j.is_oa, oa_status: j.oa_status || '', oa_url: best.url_for_pdf || best.url || '' };
  } catch (e) {
    Logger.log(`Unpaywall lookup failed: ${e}`);
    return null;
  }
}

function guessOpenFromUrl(u) {
  if (!u) return null;
  try {
    const url = new URL(u);
    if (url.host.toLowerCase().endsWith('arxiv.org')) {
      return { is_oa: true, oa_status: 'green', oa_url: u };
    }
  } catch (e) {}
  return null;
}

function pdfUrlFrom(sourceUrl, oaUrl) {
  if (oaUrl) return oaUrl;
  if (/arxiv\.org\/abs\//i.test(sourceUrl)) return sourceUrl.replace(/\/abs\//i, '/pdf/');
  return '';
}

function normalizeOaStatus(value) {
  const status = String(value || '').toLowerCase();
  return ['gold', 'green', 'bronze', 'hybrid', 'closed'].includes(status) ? status : 'unknown';
}

function translateJa(text) {
  if (!text) return '';
  try {
    return LanguageApp.translate(text, 'en', 'ja');
  } catch (e) {
    return text;
  }
}

function stripTags(s) {
  return String(s || '').replace(/<[^>]*>/g, '');
}

function decodeHtml(s) {
  const map = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'" };
  return String(s || '').replace(/(&amp;|&lt;|&gt;|&quot;|&#39;)/g, m => map[m] || m);
}

function buildPaperKey(doi, arxiv, urlNorm) {
  if (doi) return 'doi-' + slugify(doi);
  if (arxiv) return 'arxiv-' + slugify(arxiv);
  if (urlNorm) return 'url-' + Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_1, urlNorm)
    .map(byte => ('0' + (byte & 0xff).toString(16)).slice(-2))
    .join('')
    .slice(0, 12);
  return '';
}

function slugify(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 120);
}
