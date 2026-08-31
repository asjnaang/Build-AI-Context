# Composed Selection filters

The CLI has five exclusive "modes" (`all`, `category`, `path`, `mixed`, `keyword`). Non-interactive `--keywords` even ignores `--categories` and `--paths`. That is a terminal constraint, not a domain rule.

In Hosts, Selection is one composed filter: Category chips, path includes (explorer / current file / pasted paths), filename contains, content keywords. Empty filters mean "all supported" (CLI mode 1). That is CLI *capability* parity, including mixed and keyword, without the exclusive-or quirk.

Oversized files stay in the tree, warned, and unchecked by default when they exceed `max-file-lines`, matching the CLI's interactive override without a second prompt.
