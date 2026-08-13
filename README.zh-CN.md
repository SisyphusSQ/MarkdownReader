# MarkdownReader

[English](README.md)

MarkdownReader 是 Sublime Text 4 的原生 Markdown 阅读与实时预览插件。
普通 Markdown 内容由 Sublime `HtmlSheet` 展示，Mermaid 图表与 MathJax 公式
则通过本地无界面浏览器离线渲染为内嵌图片。

> 当前状态：正在开发 0.1.0。第一个原生预览纵向切片已可从源码使用，
> 尚未发布正式版本。

## 当前可用能力

- 通过 **MarkdownReader: Open Preview** 预览当前 Markdown 缓冲区。
- 通过 **MarkdownReader: Open Preview Side by Side** 在相邻 group 打开或移动预览；
  单 group 窗口会变为等宽双栏，已有多 group 布局保持不变。
- 在跟随 Sublime 主题的原生 `HtmlSheet` 中展示尚未保存的编辑内容。
- 源文档停止编辑 250ms 后自动刷新已打开的预览，不移动预览，也不抢走编辑焦点。
- 再次执行命令时复用并更新同一个预览标签页。
- 渲染标题、段落、强调、引用、列表和围栏代码块。
- 通过 Sublime 原生 minihtml 协议支持打开绝对 HTTP(S) 链接。
- 用静态 checkbox 标记展示任务列表。
- 相对已保存 Markdown 文件解析并展示本地 PNG、JPG 和 GIF；远程、缺失和不支持的
  图片显示明确占位信息。
- 其他链接协议保持不可点击，原始 HTML 会被转义。
- 通过 **MarkdownReader: Check Renderer Environment** 检查 Node.js、Chrome
  和本地 renderer 协议。
- 将 `mermaid` 围栏代码块离线渲染为透明、适配主题的 PNG，同时在图片下方
  保留原始图表源码。
- 通过本地 MathJax 将 `\(...\)` 行内公式、`$$...$$` 和 `\[...\]` 块公式
  渲染为透明 PNG。默认不启用单美元公式，避免把金额误判为公式；每个公式都提供
  **Copy TeX** 操作。

如需启用 `$...$` 行内公式，请打开 **Preferences: Package Settings →
MarkdownReader → Settings**，将 `"math_single_dollar"` 设为 `true`；默认值保持
为 `false`。

## 默认安全策略

Markdown 一律视为不可信输入。原始 HTML 会被转义，`subl:` 等非 HTTP(S) 链接
不可点击，远程图片不会加载。本地图片必须是已保存 Markdown 所在目录树内的普通
PNG、JPG 或 GIF 文件，且不超过 20 MiB；超过 2 MiB 的 Markdown 源文件不会进入
解析器，而会显示诊断信息。以上上限均按字节计算。

## 目标

- 在 Sublime 普通标签页或左右分栏中打开 Markdown 阅读视图。
- 直接预览当前编辑缓冲区，不生成临时 HTML 文件。
- 普通正文保持可选择，链接在原生 `HtmlSheet` 中可用。
- Mermaid 与 MathJax 块通过本地 Headless Chrome 离线渲染。
- 隔离单块渲染错误，并阻止陌生文档隐式访问网络。
- 保留浏览器完整预览，用于交互式图表、打印和导出。

## 兼容目标

- 计划最低支持 Sublime Text Build 4065 或更高，最终以实现所用 API 为准。
- 第一轮 PoC 以 Sublime Text 4 Build 4200 为目标。
- Sublime 插件 API 环境使用 Python 3.8。

## 设计文档

初始方案、能力边界、安全模型与 PoC 验证清单见
[docs/design/details/markdown-reader/sublime-markdown-reader.md](docs/design/details/markdown-reader/sublime-markdown-reader.md)。

仓库根目录同时也是 Sublime package 根目录。

## 从源码安装

在 macOS 上克隆仓库，并将它链接到 Sublime 的 Packages 目录：

```bash
ln -s /absolute/path/to/MarkdownReader \
  "$HOME/Library/Application Support/Sublime Text/Packages/MarkdownReader"
```

如果 Sublime 使用了其他 Packages 目录，可执行 **Preferences: Browse Packages**
确认实际位置。重新加载插件或重启 Sublime，打开 Markdown 文件，再从 Command Palette
执行 **MarkdownReader: Open Preview**。

## 开发环境

插件运行时不需要现场安装 Python 依赖；所需的 Mistune 子集已随插件 vendoring。
开发环境使用 Python 3.8 以匹配 Sublime 插件宿主，并通过 uv 创建项目内虚拟环境：

```bash
uv venv --python 3.8 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests -v
```

特殊块 renderer 需要 Node.js 22.12 或更新版本以及 Chrome 或 Chromium。
它是懒启动、可复用的 Node.js 子进程，通过 stdin/stdout 传输
newline-delimited JSON，不监听任何端口。随包资源首次使用时写入 Sublime
cache；固定版本的 Mermaid、MathJax 与 `puppeteer-core` 已提交为单文件 bundle，
终端用户无需执行 `npm install`。

## 发布

当前没有 release。首个语义化版本 tag 将在插件具备可安装能力且完成 PoC 后创建；
后续 Package Control 收录将使用本仓库的 tag-based release。

## License

[MIT](LICENSE)
