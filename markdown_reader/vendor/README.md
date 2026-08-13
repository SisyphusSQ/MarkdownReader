# Vendored dependencies

## Mistune 3.3.0

MarkdownReader bundles the Python source files required for Mistune's core
CommonMark parser and HTML renderer so a Package Control installation does not
need a separate Python package installation.

- Source: `mistune-3.3.0-py3-none-any.whl` from PyPI
- Wheel SHA-256: `a758e578acda49d8195f9a860b132dae2cf7bf409381393b1c4e6e489a65397b`
- License: BSD-3-Clause; see `mistune/LICENSE`
- Bundled subset: core block/inline/list parser, HTML renderer, plugin loader,
  table plugin, and task-list plugin

The upstream `typing_extensions.Self` import is replaced with an equivalent
local `TypeVar` because it is used only in an internal callable annotation.
Vendored modules also enable postponed annotation evaluation because Sublime
Text Build 4200 embeds Python 3.8.7, where annotations such as
`re.Pattern[str]` are not runtime-subscriptable. These packaging adaptations
keep the dependency self-contained without changing Markdown parsing behavior.
