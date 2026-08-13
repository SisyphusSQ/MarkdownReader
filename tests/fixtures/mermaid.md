# Mermaid preview proof

Normal text remains selectable above and below each special block.

```mermaid
flowchart LR
    Source[Markdown buffer] --> Renderer[Offline renderer]
    Renderer --> Preview[Transparent PNG]
```

The next block is intentionally malformed and must not hide this paragraph.

```mermaid
this is not valid Mermaid syntax
```

The preview remains usable after the isolated error.
