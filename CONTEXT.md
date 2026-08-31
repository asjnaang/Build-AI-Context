# Build AI Context

Export a project into AI-readable text artifacts so a model can cite exact paths and line ranges. This glossary is the language of the product, not of any one runtime (Python CLI, VS Code extension, or IntelliJ plugin).

## Language

**Workspace**:
The project directory the user pointed the tool at. In the CLI this is `project_root`. In an IDE it is the opened folder (VS Code) or the project base path (IntelliJ Platform).
_Avoid_: repo, root, cwd, project_root

**Catalog**:
The ordered list of supported text files discovered in the Workspace after ignore rules, binary detection, and category detection. A Catalog is the input to Selection, Filetree, and Code Graph. It is not "every file on disk."
_Avoid_: index, scan result, all files, inventory

**Category**:
A language-or-type bucket used to classify a file (python, typescript, java_kotlin, …). Categories are how users filter a Catalog, not how artifacts are formatted.
_Avoid_: language, type, extension (the suffix is how a Category is detected, not the Category itself)

**Selection**:
The subset of the Catalog chosen for bundling, plus the filters that produced it. Filters compose: categories, paths, name filters, and keywords can apply together.
_Avoid_: mode, picker, checkbox list

**Bundle**:
A numbered text file of packed file chunks, capped at 8000 rendered lines, with BEGIN/END headers so a model can recover path, Category, chunk index, and line range.
_Avoid_: dump, export file, context file, prompt pack

**Manifest**:
The JSON map of a Selection onto Bundles: per-file path, Category, hashes, line ranges, skips, and warnings.
_Avoid_: index.json, catalog.json, metadata

**Chunk**:
A contiguous slice of one source file that fits in a Bundle after header/footer overhead. One file may become several Chunks; Chunks from several files share a Bundle.
_Avoid_: split, part, page

**Filetree**:
A parseable path list of the Catalog (not the Selection): one relative path per line, trailing commas, plus type counts. Agents use it as a map of the Workspace.
_Avoid_: tree, pretty tree, directory listing

**Code Graph**:
A per-file catalog of definitions plus resolved local import edges, ordered by PageRank on those edges. Not a call graph.
_Avoid_: call graph, dependency graph, repo map (Aider's term)

**Redaction**:
Replacing secret-shaped values in Bundle bodies with `<REDACTED>`. Off by default. Distinct from skipping secret-like filenames, which is on by default.
_Avoid_: sanitization, masking, secret scan (we do not scan for leakage as a product; we optionally rewrite values)

**Agent Contract**:
The `prompt.md` copied into an export directory. It is instructions for the *downstream* model that will read the Bundles, not UI copy for the person running the tool.
_Avoid_: README, system prompt, instructions.md

**Engine**:
The module that scans a Workspace into a Catalog, applies a Selection, and writes Bundles, Manifest, Filetree, optional Code Graph, optional overview, and the Agent Contract. It has no IDE or terminal UI.
_Avoid_: core, service, backend, library (too vague), exporter (the current Python class name; keep it out of product language)

**Host**:
An IDE-specific UI that drives the Engine: the VS Code extension or the IntelliJ Platform plugin. The Python CLI is also a Host.
_Avoid_: plugin (ambiguous across IDEs), client, frontend, wrapper

**Export**:
One run of the Engine that writes a timestamped output directory (or, for Filetree/Code Graph only, files next to the Workspace). The Host may run several Exports from one Catalog without rescanning.
_Avoid_: build, compile, generate context
