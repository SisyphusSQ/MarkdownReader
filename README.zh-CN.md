# MarkdownReader

[English](README.md)

MarkdownReader 计划作为 Sublime Text 4 的原生 Markdown 阅读与实时预览插件。
普通 Markdown 内容由 Sublime `HtmlSheet` 展示，Mermaid 图表与 MathJax 公式
则通过本地无界面浏览器离线渲染为内嵌图片。

> 当前状态：仓库与工程文档已初始化；插件尚不可安装，也没有发布任何版本。

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

仓库根目录同时也是 Sublime package 根目录。只有形成可加载、可验证的纵向切片后，
才会加入运行时代码和本地渲染器；初始化提交不会暴露不可用命令或伪造占位功能。

## 发布

当前没有 release。首个语义化版本 tag 将在插件具备可安装能力且完成 PoC 后创建；
后续 Package Control 收录将使用本仓库的 tag-based release。

## License

[MIT](LICENSE)
