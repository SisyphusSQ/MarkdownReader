"""Format actionable MarkdownReader runtime diagnostics."""


def format_diagnostics(settings, environment, ping=None, renderer_error=""):
    """Return a complete diagnostics report for a message dialog."""
    ready = environment.ready and ping is not None and not renderer_error
    lines = [
        "MarkdownReader diagnostics",
        "",
        "Renderer: {}".format("READY" if ready else "NOT READY"),
        "Browser preview: bundled offline runtime",
        "",
        "Effective settings:",
        "- Refresh delay: {} ms".format(settings.refresh_delay_ms),
        "- Remote images: {}".format(
            "HTTPS opt-in enabled"
            if settings.remote_images == "allow_https"
            else "blocked"
        ),
        "- Single-dollar math: {}".format(
            "enabled" if settings.math_single_dollar else "disabled"
        ),
        "",
        "Environment:",
        "- Node: {}".format(_node_description(environment)),
        "- Chrome: {}".format(environment.chrome_path or "not found"),
    ]

    if ping is not None:
        lines.extend(
            [
                "- Protocol: {}".format(ping.get("protocolVersion", "unknown")),
                "- Mermaid: {}".format(ping.get("mermaidVersion", "unknown")),
                "- MathJax: {}".format(ping.get("mathJaxVersion", "unknown")),
                "- Puppeteer: {}".format(
                    ping.get("puppeteerVersion", "unknown")
                ),
            ]
        )

    problems = list(environment.problems)
    if renderer_error:
        problems.append("Renderer protocol check failed: {}".format(renderer_error))
    if problems:
        lines.extend(["", "Problems:"])
        lines.extend("- {}".format(problem) for problem in problems)
    if settings.warnings:
        lines.extend(["", "Settings warnings:"])
        lines.extend("- {}".format(warning) for warning in settings.warnings)
    return "\n".join(lines)


def _node_description(environment):
    if not environment.node_path:
        return "not found"
    if not environment.node_version:
        return environment.node_path
    return "{} ({})".format(environment.node_path, environment.node_version)
