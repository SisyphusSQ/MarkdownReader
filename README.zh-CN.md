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
- 源文档停止编辑后按可配置延迟（默认 250ms）自动刷新已打开的预览，不移动预览，
  也不抢走编辑焦点。
- 再次执行命令时复用并更新同一个预览标签页。
- 渲染标题、段落、强调、引用、列表和围栏代码块。
- 通过 Sublime 原生 minihtml 协议支持打开绝对 HTTP(S) 链接。
- 用静态 checkbox 标记展示任务列表。
- 相对已保存 Markdown 文件解析并展示本地 PNG、JPG 和 GIF；远程图片默认阻断，
  可显式选择只允许 HTTPS；缺失和不支持的图片显示明确占位信息。
- 其他链接协议保持不可点击，原始 HTML 会被转义。
- 通过 **MarkdownReader: Show Diagnostics** 查看有效设置、Node.js、Chrome
  和本地 renderer 各组件版本。
- 将 `mermaid` 围栏代码块离线渲染为透明、适配主题的 PNG，同时在图片下方
  保留原始图表源码。
- 通过本地 MathJax 将 `\(...\)` 行内公式、`$$...$$` 和 `\[...\]` 块公式
  渲染为透明 PNG。默认不启用单美元公式，避免把金额误判为公式；每个公式都提供
  **Copy TeX** 操作。
- 仅重新渲染发生变化的 Mermaid 与 MathJax 源码。完成结果进入共享的内存 LRU
  cache，上限为 128 项和估算 64 MiB；cache key 包含 renderer/版本及全部视觉参数。
- 通过 **MarkdownReader: Open Full Preview in Browser** 打开离线完整页面快照。
  Mermaid 以经过净化的 SVG 展示并提供缩放控件，MathJax 输出 SVG；页面提供
  **Print / Save as PDF**，可由浏览器打印或导出 PDF。

## 设置与诊断

打开 **Preferences: Package Settings → MarkdownReader → Settings** 可配置：

- `refresh_delay_ms`：原生预览防抖延迟，范围 50 至 5000ms，默认 `250`。
- `remote_images`：默认 `"blocked"`；设为 `"allow_https"` 后，原生预览可访问文档
  明确引用的 HTTPS 图片主机。离线浏览器完整预览始终阻断远程图片。
- `math_single_dollar`：是否将 `$...$` 解析为行内公式；默认 `false`，避免金额误判。
- `node_path` 与 `chrome_path`：可选的绝对可执行文件路径；空值表示自动检测。
  显式路径具有最高优先级，目标缺失或不可执行时会直接报告，不会静默回退。

有效设置变更以及 Sublime 主题/偏好变更都会刷新全部已打开的原生预览，无需重启
编辑器。无效值会回退到安全默认值，并出现在 **MarkdownReader: Show Diagnostics**
的 **Settings warnings** 中。该报告还会展示 renderer 是否就绪、当前工具路径及
protocol、Mermaid、MathJax、Puppeteer 版本。

## 默认安全策略

Markdown 一律视为不可信输入。原始 HTML 会被转义，`subl:` 等非 HTTP(S) 链接
不可点击。远程图片默认阻断；原生预览的 `"allow_https"` 选项只允许无内嵌凭据的
明确 HTTPS URL，但启用后会向对应图片主机暴露阅读者 IP 和请求元数据。本地图片
必须是已保存 Markdown 所在目录树内的普通 PNG、JPG 或 GIF 文件，且不超过 20 MiB；
超过 2 MiB 的 Markdown 源文件不会进入解析器，而会显示诊断信息。以上上限均按
字节计算。

浏览器完整预览不会把 Markdown 项目目录授权给浏览器。通过策略检查的本地图片会
转换为 data URI，原始 HTML 仍被转义，Mermaid 使用 strict 模式并移除活动链接；
Content Security Policy 会阻断网络、文件、frame、form、media 与 object 资源。
单个浏览器页面的所有内嵌本地图片另有 40 MiB 总预算。自包含 HTML 只写入操作系统
私有临时目录，不写入 Markdown 项目，并在插件卸载时清理。该页面是当前缓冲区的
一次性快照；编辑后需要重新执行命令。

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
终端用户无需执行 `npm install`。图表与公式图片只缓存在内存中，插件卸载时清空，
不会写入磁盘。独立的 browser-preview bundle 也随插件分发，在现代默认浏览器内
运行，不请求 CDN。

## 发布

当前没有 release。首个语义化版本 tag 将在插件具备可安装能力且完成 PoC 后创建；
后续 Package Control 收录将使用本仓库的 tag-based release。

## License

[MIT](LICENSE)
