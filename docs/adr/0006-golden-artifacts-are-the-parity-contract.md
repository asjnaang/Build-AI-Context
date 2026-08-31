# Golden Export artifacts are the parity contract

"The plugins do what the CLI does" is not "the same prompts." It is: given the same Workspace and Selection, the Engine writes Bundles, Manifest, Filetree, Code Graph, overview, and Agent Contract that match the Python CLI (timestamps and `created_at_utc` normalized).

Golden fixtures live in `testdata/golden/`. They are generated from the current Python CLI, then both ports must match. Format bugs (README's invented `*_readme_*.txt`, the `# ===== BEGIN FILE` example that the code does not emit) are resolved in favor of **current code**, not README.

`--update-headers`, `tools/gdwf_export.py`, `tools/universal_code_to_text_exporter.py`, and the Flet GUI are not Host features.
