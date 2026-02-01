# Google ScholarのアラートをGitHub Projectsでカンバン管理する自動化手順

Google Scholarのメール通知（アラート）を自動的にGitHub Issueとして起票し、GitHub Projects (V2) のカンバンボードでステータス管理を行うシステムの構築手順をまとめる。

Gmailに届く論文情報をGoogle Apps Script (GAS) で解析し、GitHub APIを通じてIssue化、Projectへの自動追加を行う。

## 構成
* **入力**: Gmail (Google Scholarからのアラートメール)
* **処理**: Google Apps Script (GAS)
* **出力**: GitHub Repository (Issue) + GitHub Projects (Kanban)

## 前提条件
* Googleアカウント (Gmail, GAS利用)
* GitHubアカウント

---

## 手順 1. GitHub側の準備

### 1-1. リポジトリの作成
論文管理用のリポジトリを作成する（Private推奨）。
* 例: `paper-reading-list`

### 1-2. Project (V2) の作成
1. GitHubの「Projects」から「New project」を作成する。
2. テンプレートは「Board」を選択する。
3. 作成したProjectの設定画面から、1-1で作成したリポジトリをリンクする。

### 1-3. Projectへの自動追加設定
Issueが作成された際、自動的にProjectのボードに追加されるように設定する。
1. Project画面右上の `...` メニュー > `Workflows` を開く。
2. **Auto-add to project** を有効にする。
   * ※ これにより、リポジトリにIssueが立つと自動的に「Todo (Backlog)」ステータスに追加される。

### 1-4. Access Tokenの発行
GASからAPIを叩くためのトークンを発行する。
1. [Settings > Developer settings > Personal access tokens (Tokens (classic))](https://github.com/settings/tokens) へアクセス。
2. `Generate new token (classic)` を選択。
3. **Scopes** 設定で **`repo`** (Full control of private repositories) にチェックを入れる。
4. 生成されたトークン（`ghp_...`）を控えておく。

---

## 手順 2. Google Apps Script (GAS) の設定

### 2-1. プロジェクトの作成
[Google Apps Script](https://script.google.com/) にアクセスし、新しいプロジェクトを作成する。

### 2-2. スクリプトプロパティの設定
コード内に認証情報を直書きしないよう、環境変数を設定する。
GASエディタ左側の「プロジェクトの設定（歯車アイコン）」>「スクリプトプロパティ」に以下を追加する。

| プロパティ名 | 設定値の例 | 説明 |
| :--- | :--- | :--- |
| `GITHUB_TOKEN` | `ghp_xxxx...` | 手順1-4で発行したトークン |
| `GITHUB_OWNER` | `username` | GitHubのユーザー名 |
| `GITHUB_REPO` | `paper-reading-list` | 手順1-1で作成したリポジトリ名 |
| `UNPAYWALL_EMAIL` | `email@example.com` | Unpaywall API利用のためのメアド |
| `LABELS_JSON` | `["Author Name", "Keyword"]` | 検索対象のGmailラベル（JSON配列形式） |
| `DAYS_LOOKBACK` | `7` | 検索対象とする過去の日数 |

※ Gmail側でScholarからのメールにフィルタをかけ、`LABELS_JSON` で指定したラベルが自動付与されるようにしておくこと。

### 2-3. コードの実装
`Code.gs` に以下のコードを記述する。
（Unpaywall APIによるOA判定、GitHub Search APIによる重複排除機能を含む）

```javascript
/** ====== 設定読み込み ====== */
function cfg() {
  const props = PropertiesService.getScriptProperties();
  return {
    GITHUB_TOKEN: props.getProperty('GITHUB_TOKEN'),
    GITHUB_OWNER: props.getProperty('GITHUB_OWNER'),
    GITHUB_REPO:  props.getProperty('GITHUB_REPO'),
    UNPAYWALL_EMAIL: props.getProperty('UNPAYWALL_EMAIL'),
    LABELS: JSON.parse(props.getProperty('LABELS_JSON') || '[]'),
    DAYS_LOOKBACK: Number(props.getProperty('DAYS_LOOKBACK') || '7')
  };
}

/** ====== メイン処理 ====== */
function runHarvest() {
  const C = cfg();
  if (!C.GITHUB_TOKEN || !C.GITHUB_OWNER || !C.GITHUB_REPO) {
    throw new Error('スクリプトプロパティの設定が不足しています');
  }

  const afterQuery = formatAfterQuery(C.DAYS_LOOKBACK);
  let processedCount = 0;

  C.LABELS.forEach(label => {
    // ラベルごとの検索クエリ
    const q = buildQueryForLabel(label, afterQuery);
    // API制限考慮のため処理数を制限（1回あたり10スレッド程度）
    const threads = GmailApp.search(q, 0, 10); 
    
    threads.forEach(th => {
      const msgs = th.getMessages();
      msgs.forEach(msg => {
        if (!msg.isUnread()) return;

        const html = msg.getBody();
        const raw = msg.getRawContent();
        const entries = extractScholarEntriesRobust(html, raw);

        entries.forEach(e => {
          processEntry(e, label, C);
          processedCount++;
          Utilities.sleep(1500); // GitHub APIレート制限回避
        });

        if (entries.length > 0) {
          msg.markRead();
        }
      });
    });
  });
  console.log(`Processed: ${processedCount}`);
}

/** ====== 個別エントリ処理 ====== */
function processEntry(e, label, C) {
  const finalUrl = expandScholarRedirect(e.url);
  const normUrl = normalizeUrl(finalUrl || e.url);
  const meta = resolveMetadata({ title: e.title, url: finalUrl || e.url });
  const oa = meta.doi ? unpaywallLookup(meta.doi, C.UNPAYWALL_EMAIL) : guessOpenFromUrl(finalUrl);
  
  // 重複キー生成
  const dupKey = buildDupKey(meta.doi, meta.arxiv, normUrl);
  if (!dupKey) return;

  // GitHub上の重複チェック
  if (existsInGitHub(C, dupKey)) {
    console.log(`Skipping duplicate: ${dupKey}`);
    return;
  }

  // Issue作成
  createGitHubIssue(C, {
    title: e.title,
    body: createIssueBody(e, meta, oa, dupKey, label, finalUrl),
    labels: ['scholar-alert', label]
  });
}

/** ====== GitHub API連携 ====== */
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
    if (res.getResponseCode() !== 200) return false;
    return JSON.parse(res.getContentText()).total_count > 0;
  } catch (e) { return false; }
}

function createGitHubIssue(config, payload) {
  const url = `https://api.github.com/repos/${config.GITHUB_OWNER}/${config.GITHUB_REPO}/issues`;
  UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: { 
      'Authorization': `Bearer ${config.GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github.v3+json'
    },
    payload: JSON.stringify(payload)
  });
}

function createIssueBody(entry, meta, oa, dupKey, label, finalUrl) {
  const snipJa = translateJa(entry.snippet); 
  const titleJa = translateJa(entry.title);
  const authors = meta.authors || entry.authorLine || 'N/A';
  let oaStatus = '❓ Unknown';
  if (oa && oa.is_oa) oaStatus = `✅ **Available** ${oa.oa_url ? `([PDF](${oa.oa_url}))` : ''}`;
  else if (oa && !oa.is_oa) oaStatus = '❌ Closed';

  return `
## ${titleJa || entry.title}
- **Authors:** ${authors}
- **Venue:** ${meta.venue || ''} ${meta.year ? `(${meta.year})` : ''}
- **Link:** ${meta.doi ? `[DOI](https://doi.org/${meta.doi})` : ''} ${meta.arxiv ? `[arXiv](https://arxiv.org/abs/${meta.arxiv})` : ''} [Source](${finalUrl || entry.url})
- **OA Status:** ${oaStatus}

### Abstract (Translated)
${snipJa}

### Original Snippet
> ${entry.snippet}

---
_Label: ${label}_
`;
}

/** ====== ユーティリティ関数群 ====== */
function formatAfterQuery(d) {
  const date = new Date(); date.setDate(date.getDate() - d);
  return `after:${date.getFullYear()}/${String(date.getMonth()+1).padStart(2,'0')}/${String(date.getDate()).padStart(2,'0')}`;
}
function buildQueryForLabel(l, a) { return `label:"${l}" ${a}`; }
function translateJa(t) { try { return t ? LanguageApp.translate(t, 'en', 'ja') : ''; } catch(e){ return t; } }
function buildDupKey(doi, arxiv, url) {
  if (doi) return `doi:${doi.toLowerCase()}`;
  if (arxiv) return `arxiv:${arxiv.toLowerCase()}`;
  return url ? `url:${url.toLowerCase()}` : '';
}
function expandScholarRedirect(u) {
  try { return decodeURIComponent(u.split('url=')[1].split('&')[0]); } catch(e) { return u; }
}
function normalizeUrl(u) {
  try { const U = new URL(u); ['utm_source','ref'].forEach(k=>U.searchParams.delete(k)); return U.href; } catch(e){ return u; }
}
// ※HTML抽出ロジック（extractScholarEntriesRobustなど）は長くなるため省略。
// 必要に応じてScholarのHTML構造に合わせた正規表現パーサーを実装する。
function extractScholarEntriesRobust(h,r){return[];} // ダミー
function resolveMetadata(s){return{};} // ダミー
function unpaywallLookup(d,e){return null;} // ダミー
function guessOpenFromUrl(u){return null;} // ダミー