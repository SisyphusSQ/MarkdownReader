---
name: release
description: Prepare and publish a versioned MarkdownReader GitHub release. Use when the user explicitly asks to release, tag, package, or publish a MarkdownReader version, or asks to repeat the repository's established release workflow.
---

# MarkdownReader release

按本仓库既有的“release 分支 → release PR → 合入 main → 冻结提交 → tag → 资产 → GitHub Release”顺序完成发版。只在用户明确授权发布时执行远端写操作；任何门禁失败都停在当前阶段，不用 force push、删除分支、覆盖 tag 或伪造成功。

## 1. 读取当前约定并确认范围

- 读取当前目录及父目录适用的全部 `AGENTS.md`，再读取 `CHANGELOG.md`、中英文 README、`docs/release-notes/`、`scripts/build_release_package.py`、`pyproject.toml` 和 `.gitignore`。
- 确认仓库为 `SisyphusSQ/MarkdownReader`，默认分支通过 GitHub 元数据确认，不能猜测 `main` 或 `master`。
- 确认工作区干净、当前不在 detached HEAD、远端可访问，并先将本地默认分支同步到最新 `origin/<default>`。
- 读取现有 tag 和 GitHub Release，确认目标版本不存在。当前仓库的实际 tag 是裸版本号（例如 `0.1.0`、`0.2.0`），不是带 `v` 前缀；除非用户明确改变约定，否则继续使用裸版本号。
- 将版本号标准化为 `X.Y.Z`，用当前日期写入 changelog 和 release notes；不要猜测或复用旧版本的手工验证结论。

## 2. 创建 release-prep 分支和内容

从干净且已同步的默认分支创建 `suqing/release-<version>`，分支名只使用英文、数字、`-`、`_` 和 `/`。

更新以下内容：

- 将 `CHANGELOG.md` 的 `Unreleased` 条目归档到 `## <version> - YYYY-MM-DD`，保留空的 `## Unreleased`。
- 更新 `README.md` 与 `README.zh-CN.md` 的最新版本、安装链接、release-notes 链接和版本相关验证边界。
- 新建 `docs/release-notes/<version>.md`，至少写明亮点、安装方式、依赖、自动化证据、人工验证边界、安全限制和 Package Control 是否在范围内。
- 不把 `dist/`、测试结果临时文件、源码 checkout、`node_modules` 或凭据写入提交。

提交前分别执行：

```bash
git diff --check
git diff --name-status
git diff --stat
```

检查 staged 文件名和 staged 内容的敏感格式（私钥、token、连接串、凭据）；发现可疑内容时停止并只报告文件位置，不回显值。遵守当前项目 `AGENTS.md` 的提交/发版测试规则；本项目的提交收尾不重复执行本地测试，自动化验证以 release PR 的 GitHub CI 为准。

提交 release-prep commit，使用类似 `chore: prepare <version> release` 的准确信息；普通 push 到 `origin/suqing/release-<version>`，不得 force push。

## 3. 创建、验证并合并 release PR

- 检查当前 source→default 是否已有开放 PR；唯一匹配项复用，多个匹配项停止。
- PR 标题和正文使用中文，写清版本、归档文件、tag 命名和验证边界。
- 目标 PR 必须是非 Draft，并回读 source、target 与 head SHA。
- 等待以下仓库 CI 到终态且全部通过：`Python 3.8`、`Python 3.12`、`Renderer bundle`。这些检查分别覆盖 ruff/unit tests、renderer 依赖审计、可复现 bundle 和完整 browser preview；空 status、运行中或 unknown 都不能当作通过。
- 使用与历史 release 一致的 merge commit 方式，传入预期 head SHA；确认平台返回 `merged=true`、PR URL 和真实 merge commit SHA。
- `git fetch origin` 后切到默认分支，只执行 `git pull --ff-only`。回读工作区干净、本地 HEAD、upstream SHA 和 `origin/<default>` SHA 一致；否则停止，不自行修复历史。

## 4. 冻结提交、打 tag 并构建资产

只在上述合并后的干净默认分支上操作：

```bash
git tag -a <version> -m "MarkdownReader <version>"
git rev-parse <version>^{}
git push origin <version>
```

确认 annotated tag 的 peeled commit 等于冻结的 release merge commit，远端 tag 同时存在 tag object 和 peeled commit；tag 已存在、指向错误提交或远端已存在时停止，禁止覆盖。

使用项目既有 Python 3.8 环境构建，不把产物提交回 Git：

```bash
.venv/bin/python scripts/build_release_package.py \
  --checksum-output dist/SHA256SUMS
```

构建后必须验证：

- `dist/MarkdownReader.sublime-package` 和 `dist/SHA256SUMS` 存在，记录包字节数和 SHA-256。
- 在两个文件所在目录执行 `shasum -a 256 -c SHA256SUMS`；checksum 使用 basename，所以不要从仓库根目录执行该命令。
- `unzip -t dist/MarkdownReader.sublime-package` 通过；必需运行时文件存在，`tests/`、`docs/`、`scripts/`、`.git/`、`node_modules/`、`__pycache__/`、`.pyc`、开发依赖和 renderer 源码不在包内。
- 重复执行构建并比较两次 package SHA，确认构建确定性；校验只写入被 `.gitignore` 忽略的 `dist/`。

## 5. 创建公开 GitHub Release 并回读

默认创建公开、非 Draft、非 prerelease 的 Release；只有用户明确要求时才改变可见性。上传且只上传：

- `dist/MarkdownReader.sublime-package`
- `dist/SHA256SUMS`

Release 标题使用 `MarkdownReader <version>`，正文使用中文，包含亮点、安装命令、冻结提交、CI 结果、人工验证未覆盖范围、Package Control 边界和 package SHA-256。创建后回读：

```bash
gh release view <version> --repo SisyphusSQ/MarkdownReader \
  --json tagName,isDraft,isPrerelease,targetCommitish,assets,url
```

逐项核对 tag、目标提交、资产名、大小、状态和 GitHub digest 与本地结果一致。再从公开下载 URL 读取两个资产并计算 SHA-256；公网下载成功才可报告资产已公开可取。Release API 读不到某个字段时，不把单次缺失响应解释为 Release 不存在，改用 Release 列表、tag 和资产 URL 交叉确认。

## 6. 结束条件和失败边界

只有同时满足以下条件才报告完成：

- 默认分支工作区干净，local HEAD、upstream 和远端默认分支 SHA 一致。
- `<version>` annotated tag 的 peeled commit 等于冻结 release commit，远端 tag 可读。
- GitHub Release 为目标版本、公开、非 Draft、非 prerelease，两个资产均 uploaded。
- 本地 checksum、GitHub digest 和公网下载 digest 一致。
- 报告 PR URL、merge SHA、tag/commit、资产大小与 SHA、Release URL，以及未执行的人工验证或外部流程。

任一步失败时，准确报告已完成到 release-prep 提交、PR 创建、PR 合并、默认分支更新、tag 推送、资产构建、Release 创建或公网回读的哪一步。不要删除源分支，不要把 CI 通过升级为 Sublime/生产人工 E2E，也不要把 Package Control 提交写成已完成。
