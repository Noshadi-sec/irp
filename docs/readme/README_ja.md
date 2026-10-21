<div align="center">

[English](../../README.md) · [简体中文](README_zh.md) · **日本語** · [한국어](README_ko.md) · [Español](README_es.md) · [Italiano](README_it.md)

# IRP：どんな論文も実装し、すべての主張を検証する。

### コーディングエージェントが研究論文を動くコードに変え、実行し、主張ごとにどこまで再現できたかを証明するための MCP サーバーと CLI。

**論文を渡せば、動くコードと、エージェントを信頼しなくても検証できるレポートが返ってきます。**

[![PyPI version](https://img.shields.io/pypi/v/irp?style=flat-square&color=3775a9)](https://pypi.org/project/irp-agents/)
[![MCP tool catalog](https://img.shields.io/badge/MCP-tool_catalog-5c4ee5?style=flat-square)](../mcp-contracts.md#generated-catalog)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776ab?style=flat-square&logo=python&logoColor=white)](#再現できるもの)
[![MIT license](https://img.shields.io/badge/license-MIT-f4c430?style=flat-square)](../../LICENSE)

[クイックスタート](#クイックスタート) · [仕組み](#仕組み) · [レポート](#レポート) · [再現できるもの](#再現できるもの) · [FAQ](#faq) · [ドキュメント](#ドキュメント)

<code>uvx irp-agents setup</code>

</div>

> [!IMPORTANT]
> IRP は [Noshadi-sec/irp](https://github.com/Noshadi-sec/irp) または
> [PyPI の irp パッケージ](https://pypi.org/project/irp-agents/) から入手してください。
> 似たリポジトリ名やコピーされた README は、公式の配布元であることを意味しません。

<div align="center">

<img src="../assets/irp-flow.svg" alt="IRP の流れ：あなたがエージェントに論文の実装を依頼し、エージェントは論文を読み、主張を記録し、コードを書き、IRP のツールで実行を決めます。IRP は論文の取得とコードの実行を行い、すべての手順をハッシュチェーンの証拠ログに記録します。レポートはそのログだけから書かれます。" width="900" />

</div>

---

コードのない論文や、信頼できないコードの論文を見つけたら、IRP を使ってエージェントに
実装させましょう。エージェントは論文を読み、論文が主張するすべての数値を記録し、実装を書き、
実行して結果を比較します。IRP は取得・実行・記録を担当し、近道を拒否します。
手入力した数値は決してカウントされず、短縮した実行も決してカウントされず、
レポートは証拠ログだけから書かれます。

IRP はエージェント（Claude Code、Codex、Cursor）を、論文の取り込み、環境、実行、測定、
判定のためのツールにつなぎます。同じツールはターミナルからも使えます。すべてはローカルで動作し、
IRP 自身がモデルを呼び出すことはありません。

## クイックスタート

### エージェントを設定する

[uv](https://docs.astral.sh/uv/) をインストールしてから実行します：

```bash
uvx irp-agents setup
```

設定するエージェントを選び、提案された変更を確認して承認します。setup は IRP の MCP
サーバーとワークフロースキルを追加し、既存の設定をバックアップします。終わったらエージェントを
再起動してください。

setup は Claude Code、Codex、Cursor に対応しています。その他の MCP クライアントは
[手動登録](../installation.md#manual-registration) を使えます。

### エージェントに頼む

```text
Build arXiv 2501.12345 and check Table 2.
```

動くコードのフォルダーとレポート（各主張、論文の数値、あなたの数値、判定）が返ってきます。

### ターミナルを使う

すべてのツールはコマンドとしても使えます。論文を新しいスタディに取得してアウトラインを読みます：

```bash
irp fetch 2501.12345 --study ~/studies/example
irp section index --study ~/studies/example
```

常用するなら `irp` コマンドをインストールします：

```bash
uv tool install irp-agents
irp --help
```

ターミナルでの全手順は [CLI ガイド](../cli.md) を参照してください。

### 準備状況を確認する

```bash
irp doctor
```

doctor は Python、uv、git、Docker、GPU、ディスク容量、エージェントの登録を確認し、何も変更しません。

### IRP を更新する

```bash
irp update
```

uvx を使う場合は `uvx irp-agents@latest setup` でエージェントの設定を更新し、計画を確認してから
エージェントを再起動します。

## 仕組み

エージェントが考え、IRP が実行して記録を残します。エージェントは論文を読み、コードを書き、
何を実行するかを決めます。すべての操作は一つのコアを通るため、CLI と MCP サーバーは同じように
振る舞い、すべての手順は追記専用でハッシュチェーンされた証拠ログに残ります。レポートはこの
ログだけから作られます。

| 段階 | ツール | 役割 |
| --- | --- | --- |
| 取り込み | `fetch_paper` | arXiv の LaTeX ソースまたは PDF をダウンロードし、ハッシュを取り、セクションに分割 |
| 取り込み | `get_section`、`get_page_image` | ファイル名と行番号付きのセクション本文、または数式や図のためのページ画像を返す |
| 主張 | `add_claim`、`list_claims` | 指標、値、掲載箇所、成功基準とともに各主張を記録 |
| 計画 | `add_guess` | 論文が省いた詳細、選んだ値、その理由を記録 |
| 計画 | `map_method` | 数式やアルゴリズムの手順をファイルと行に対応付け |
| 構築 | `create_env` | uv 環境または Docker イメージを作り、ロックファイルを書く |
| 実行 | `run`、`run_status` | コマンドを一つ実行し、出力、終了コード、時間、メモリ、シード、コミット、ファイルを保存 |
| 実行 | `run_remote` | 費用見積もりと承認の後、有料 GPU で同じことを行う |
| 測定 | `extract_metrics` | ログや結果ファイルから数値をファイル名と行番号付きで抽出 |
| 判定 | `compare`、`add_note` | 主張と測定値を並べ、四つの判定のいずれかを下す |
| レポート | `report`、`verify`、`study_status` | ログから report.md と report.json を書き、ハッシュチェーンを再検証 |

ワークフロースキルはエージェントに六つの厳格なルールを与え、ツールは可能な限りそれを強制します：

1. 数値を結果として入力・推定・コピーしない。
2. 実行を成功させるために論文の手法を変えない。代わりに推測として記録する。
3. 無理に進めず、ブロックしたエラーとともに「実行できない」と報告する。
4. まず最小の忠実な版を実行する。短縮した実行は決してカウントされない。
5. コードを書く前にすべての主張を記録する。
6. 有料の計算の前には必ず確認する。

## レポート

レポートこそが製品です。人がエージェントを信頼せずにすべての判定を検証できなければなりません。
レポートは五つの部分からなります：主張の表、四つの判定（再現、近い、この実行では再現せず、
実行できない）、推測の一覧、数式からコード行への手法マップ、そして来歴（arXiv ID とバージョン、
ファイルハッシュ、git コミット、ロックファイル、GPU、シード、終了コード付きの全コマンド、
ハッシュチェーンを再検証する verify コマンド）。

すべての主張に証拠付きの判定がそろうまで、エージェントは作業を終えられません。

`report.md` の例（架空の数値）：

```markdown
# Reproduction report: Example Paper (arXiv 2501.12345v2)

Result: 2 reproduced, 1 close, 1 could not run (of 4 claims)

| Claim | Where | Paper | Ours | Verdict |
| --- | --- | --- | --- | --- |
| c1 Test accuracy | Table 2, row 3 | 94.1% | 93.8% (3 seeds, std 0.2) | close |
| c2 Training loss | Figure 4 | 0.31 | 0.31 (3 seeds) | reproduced |
| c3 Speed-up | Section 5.2 | 2.0x | 2.1x | reproduced |
| c4 ImageNet top-1 | Table 3 | 81.2% | not run: needs 8 GPUs for 2 days | could not run |
```

各フィールドは [証拠とレポート](../evidence-and-report.md) を参照してください。

## 再現できるもの

IRP には macOS または Linux 上の Python 3.11+ が必要です。その他のツールは論文によります：

| 必要なもの | IRP が使うもの | 要件とガイド |
| --- | --- | --- |
| 論文の取り込み | arXiv の LaTeX ソースを優先、次に PDF。数式と図にはページ画像 | arXiv へのアクセス；[論文の取り込み](../paper-intake.md) |
| よりよい PDF 構造 | テキストと表に Docling | 任意 `irp-agents[docling]` |
| 環境 | ロックファイル付きの uv 仮想環境、または隔離用の Docker イメージ | uv または Docker；[環境](../environments.md) |
| 計算 | 手元の CPU や GPU；費用見積もりと承認後の Modal GPU サンドボックス（実験的） | 任意 `irp-agents[modal]`；[計算](../compute.md) |
| エージェント | Claude Code、Codex、Cursor；その他の MCP クライアントは手動 | [インストール](../installation.md) |

IRP は計算系の論文（機械学習、アルゴリズム、シミュレーション）を対象とします。
ウェットラボの実験や兵器に関わるものは対象外です。

## ショーケース

ショーケースはまだ公開していません。各ショーケースは独自のリポジトリとレポートを持ちます。
進捗は [ロードマップ](../roadmap.md) を参照してください。

## FAQ

<details>
<summary><strong>どのエージェントで使えますか？</strong></summary>

ローカルの MCP サーバーに対応したエージェントなら使えます。setup は Claude Code、Codex、Cursor を設定します。

</details>

<details>
<summary><strong>IRP は AI モデルを呼び出したり、論文をアップロードしたりしますか？</strong></summary>

しません。頭脳はあなたのエージェントで、IRP はモデルを呼ばず API キーも持ちません。
arXiv から論文をダウンロードし、uv または Docker でパッケージを入れ、あなたのマシンでコードを実行します。

</details>

<details>
<summary><strong>論文のコードを実行しても安全ですか？</strong></summary>

uv 仮想環境はサンドボックスではなく、コードはあなたの権限で動きます。自分で書いていない、
あるいは信頼できないコードには `backend: "docker"` を使ってください。[セキュリティポリシー](../../SECURITY.md) も参照。

</details>

<details>
<summary><strong>「再現せず」とはどういう意味ですか？</strong></summary>

この実行（記録した推測を含む）が、定めた基準の範囲で論文の数値に届かなかったという意味です。
レポートには「not reproduced by this run」と書かれ、すべての推測が列挙されます。一回の試みに
ついての証拠であって、論文への判決ではありません。公表する前に著者へ連絡してください。

</details>

<details>
<summary><strong>IRP はお金を使いますか？</strong></summary>

ターミナルで `irp budget` により価格と予算を記録し、エージェントが示した見積もりを
承認した場合にのみ、有料 GPU を使います。実行時間の上限は見積もりの時間と同じです。

</details>

## ドキュメント

- [インストールとセットアップ](../installation.md)
- [CLI](../cli.md)
- [MCP 契約](../mcp-contracts.md) と [プロンプト](../mcp-prompts.md)
- [証拠とレポート](../evidence-and-report.md)
- [論文の取り込み](../paper-intake.md)、[環境](../environments.md)、[計算](../compute.md)
- [ベンチマーク](../benchmarks.md) と [ロードマップ](../roadmap.md)

脆弱性は [SECURITY.md](../../SECURITY.md) から報告してください。

## 免責事項

責任ある利用については [DISCLAIMER.md](../../DISCLAIMER.md) を参照してください。「再現せず」の判定は
一回の実行についての証拠であり、論文や著者への評価ではありません。

## コントリビュート

貢献を歓迎します。開発環境は [CONTRIBUTING.md](../../CONTRIBUTING.md) を参照してください。

## ライセンス

[MIT](../../LICENSE)。第三者の素材はそれぞれのライセンスに従います。[第三者通知](../../THIRD_PARTY_NOTICES.md) を参照。
