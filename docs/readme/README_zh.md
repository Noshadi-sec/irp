<div align="center">

[English](../../README.md) · **简体中文** · [日本語](README_ja.md) · [한국어](README_ko.md) · [Español](README_es.md) · [Italiano](README_it.md)

# IRP：复现任何论文，验证每一个结论。

### 一个 MCP 服务器和命令行工具：让你的编程智能体把研究论文变成可运行的代码，运行它，并逐条证明结果与论文有多接近。

**给它一篇论文，得到可运行的代码，以及一份无需信任智能体即可核验的报告。**

[![PyPI version](https://img.shields.io/pypi/v/irp?style=flat-square&color=3775a9)](https://pypi.org/project/irp-agents/)
[![MCP tool catalog](https://img.shields.io/badge/MCP-tool_catalog-5c4ee5?style=flat-square)](../mcp-contracts.md#generated-catalog)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776ab?style=flat-square&logo=python&logoColor=white)](#可以复现什么)
[![MIT license](https://img.shields.io/badge/license-MIT-f4c430?style=flat-square)](../../LICENSE)

[快速开始](#快速开始) · [工作原理](#工作原理) · [报告](#报告) · [可以复现什么](#可以复现什么) · [常见问题](#常见问题) · [文档](#文档)

<code>uvx irp-agents setup</code>

</div>

> [!IMPORTANT]
> 请只从 [Noshadi-sec/irp](https://github.com/Noshadi-sec/irp) 或
> [PyPI 上的 irp 包](https://pypi.org/project/irp-agents/) 获取 IRP。
> 相似的仓库名或复制的 README 并不能证明下载来源是官方的。

<div align="center">

<img src="../assets/irp-flow.svg" alt="IRP 流程：你让智能体复现一篇论文；智能体阅读论文、记录结论、编写代码并通过 IRP 的工具决定运行；IRP 获取论文、运行代码，并把每一步写入哈希链证据日志；报告只根据该日志生成。" width="900" />

</div>

---

找到一篇没有代码的论文，或者代码不可信？让你的智能体用 IRP 复现它。
智能体阅读论文，记录论文声称的每一个数字，编写实现，运行并比较结果。
IRP 负责获取、运行和留存记录，并拒绝走捷径：手工输入的数字永远不算数，
缩短的运行永远不算数，报告只根据证据日志生成。

IRP 把你的智能体（Claude Code、Codex 或 Cursor）连接到论文读取、环境、
运行、度量和判定等工具。你也可以在终端中使用同样的工具。一切都在本地运行；
IRP 从不调用任何模型，数据只会发送到你指定的地方。

## 快速开始

### 配置你的智能体

安装 [uv](https://docs.astral.sh/uv/) 后运行：

```bash
uvx irp-agents setup
```

选择要配置的智能体，查看拟议的更改并批准。setup 会添加 IRP 的 MCP
服务器和工作流技能，并备份已有配置。完成后重启智能体。

setup 支持 Claude Code、Codex 和 Cursor。其他 MCP 客户端可以
[手动注册](../installation.md#manual-registration)。

### 向智能体提问

```text
Build arXiv 2501.12345 and check Table 2.
```

你会得到一个可运行的代码目录和一份报告：每个结论、论文的数字、你的数字以及判定结果。

### 使用终端

每个工具都是一个命令。把论文获取到新的研究目录并查看大纲：

```bash
irp fetch 2501.12345 --study ~/studies/example
irp section index --study ~/studies/example
```

长期使用时安装 `irp` 命令：

```bash
uv tool install irp-agents
irp --help
```

完整的终端工作流见 [CLI 指南](../cli.md)。

### 检查就绪状态

```bash
irp doctor
```

doctor 检查 Python、uv、git、Docker、GPU、磁盘空间和智能体注册情况，不做任何修改。

### 更新 IRP

```bash
irp update
```

使用 uvx 时，运行 `uvx irp-agents@latest setup` 刷新智能体配置，查看计划后重启智能体。

## 工作原理

智能体负责思考；IRP 负责执行并保存凭据。智能体阅读论文、编写代码并决定运行什么。
每个操作都经过同一个核心，因此 CLI 和 MCP 服务器行为一致，每一步都写入只追加、
哈希链接的证据日志。报告只根据这份日志生成。

| 阶段 | 工具 | 作用 |
| --- | --- | --- |
| 读取 | `fetch_paper` | 下载 arXiv LaTeX 源码或 PDF，计算哈希，按章节切分 |
| 读取 | `get_section`、`get_page_image` | 返回带文件名和行号的章节文本，或用于公式和图表的页面图像 |
| 结论 | `add_claim`、`list_claims` | 记录每个结论：指标、数值、出处和成功标准 |
| 计划 | `add_guess` | 记录论文遗漏的细节、所做的选择及理由 |
| 计划 | `map_method` | 把公式或算法步骤链接到代码文件和行 |
| 构建 | `create_env` | 创建 uv 环境或 Docker 镜像并写入锁文件 |
| 运行 | `run`、`run_status` | 运行一条命令，保存输出、退出码、时间、内存、种子、提交和文件 |
| 运行 | `run_remote` | 在付费 GPU 上运行，需先给出费用估算并获得批准 |
| 度量 | `extract_metrics` | 从日志和结果文件中提取数字，附带文件和行号 |
| 判定 | `compare`、`add_note` | 将结论与测量并列，给出四种判定之一 |
| 报告 | `report`、`verify`、`study_status` | 根据日志写出 report.md 和 report.json；重新校验哈希链 |

工作流技能给智能体六条硬性规则，工具会尽可能强制执行：

1. 永远不要把数字当作结果手工输入、估计或复制。
2. 永远不要为了让运行成功而改变论文的方法；改为记录一个猜测。
3. 无法运行时，报告“无法运行”并附上阻塞错误，而不是硬推。
4. 先运行最小的忠实版本；缩短的运行永远不算数。
5. 编写任何代码之前先记录每个结论。
6. 任何付费计算之前先询问。

## 报告

报告就是产品：人必须能在不信任智能体的情况下核验每一个判定。它包含五部分：结论表、
四种判定（已复现、接近、本次运行未复现、无法运行）、猜测列表、从公式到代码行的方法映射，
以及来源信息（arXiv ID 和版本、文件哈希、git 提交、锁文件、GPU、种子、每条命令及其退出码，
以及重新校验哈希链的 verify 命令）。

在每个结论都有带证据的判定之前，智能体无法结束任务。

`report.md` 示例（虚构数字）：

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

每个字段的说明见 [证据与报告](../evidence-and-report.md)。

## 可以复现什么

IRP 需要 macOS 或 Linux 上的 Python 3.11+。其他工具取决于论文：

| 需求 | IRP 使用 | 要求和指南 |
| --- | --- | --- |
| 论文读取 | 优先 arXiv LaTeX 源码，其次 PDF，并提供用于公式和图表的页面图像 | 可访问 arXiv；[论文读取](../paper-intake.md) |
| 更好的 PDF 结构 | Docling 提取文本和表格 | 可选 `irp-agents[docling]` |
| 环境 | 带锁文件的 uv 虚拟环境，或用于隔离的 Docker 镜像 | uv 或 Docker；[环境](../environments.md) |
| 计算 | 你的 CPU 或 GPU；经费用估算和批准后的 Modal GPU 沙箱（实验性） | 可选 `irp-agents[modal]`；[计算](../compute.md) |
| 智能体 | Claude Code、Codex、Cursor；其他 MCP 客户端可手动注册 | [安装](../installation.md) |

IRP 支持计算类论文：机器学习、算法和模拟。不支持湿实验或任何与武器相关的工作。

## 展示案例

目前尚未发布展示案例。每个展示案例都会有自己的仓库和报告。进度见 [路线图](../roadmap.md)。

## 常见问题

<details>
<summary><strong>哪些智能体可以使用 IRP？</strong></summary>

任何支持本地 MCP 服务器的智能体。setup 可配置 Claude Code、Codex 和 Cursor。

</details>

<details>
<summary><strong>IRP 会调用 AI 模型或上传我的论文吗？</strong></summary>

不会。你的智能体是大脑；IRP 从不调用模型，也没有 API 密钥。它从 arXiv
下载论文，通过 uv 或 Docker 安装软件包，并在你的机器上运行代码。

</details>

<details>
<summary><strong>运行论文的代码安全吗？</strong></summary>

uv 虚拟环境不是沙箱：代码以你的权限运行。对于不是你编写或不信任的代码，请使用
`backend: "docker"`。见 [安全策略](../../SECURITY.md)。

</details>

<details>
<summary><strong>“未复现”是什么意思？</strong></summary>

表示这次运行（连同记录的猜测）没有在给定标准内达到论文的数字。报告写作
“not reproduced by this run”，并列出每一个猜测。这是关于一次尝试的证据，
而不是对论文的裁决；公开之前请先联系作者。

</details>

<details>
<summary><strong>IRP 会花钱吗？</strong></summary>

只有在你在终端用 `irp budget` 记录了价格和预算，并批准了智能体展示的估算之后，
才会使用付费 GPU。运行时间上限等于估算的小时数。

</details>

## 文档

- [安装与配置](../installation.md)
- [CLI](../cli.md)
- [MCP 契约](../mcp-contracts.md) 与 [提示](../mcp-prompts.md)
- [证据与报告](../evidence-and-report.md)
- [论文读取](../paper-intake.md)、[环境](../environments.md)、[计算](../compute.md)
- [基准](../benchmarks.md) 与 [路线图](../roadmap.md)

通过 [SECURITY.md](../../SECURITY.md) 报告漏洞。

## 免责声明

负责任使用的说明见 [DISCLAIMER.md](../../DISCLAIMER.md)。“未复现”的判定是关于一次运行的证据，
不是对论文或作者的评判。

## 贡献

欢迎贡献。开发设置见 [CONTRIBUTING.md](../../CONTRIBUTING.md)。

## 许可证

[MIT](../../LICENSE)。第三方材料保留其各自的许可证，见 [第三方声明](../../THIRD_PARTY_NOTICES.md)。
