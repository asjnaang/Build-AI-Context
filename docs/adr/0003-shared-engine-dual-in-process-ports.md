# Shared Engine contract; TypeScript and Kotlin in-process ports

The Engine must not require Python. VS Code Hosts run TypeScript in-process. IntelliJ Hosts run Kotlin/JVM in-process. Neither user population should be asked to install the other's runtime (Node in IntelliJ, JRE in VS Code, Python in either).

So there is one **contract** (policy JSON, artifact formats, golden fixtures) and two **in-process ports** of the Engine: TypeScript for VS Code, Kotlin for IntelliJ. Python `baic` remains the CLI Host and the v1 parity oracle: CI fails a port that does not match golden Export artifacts from the current CLI.

**Considered options:** shell out to `baic` (fails the no-Python requirement); freeze Python into a sidecar binary (size, antivirus, notarization, no VS Code Web later, tree-sitter wheels); one Rust/Go binary bundled in both Hosts (best single implementation, high rewrite cost, signing per platform); TypeScript compiled to a native binary for IntelliJ (one language, fragile packaging). Dual in-process ports plus golden tests is the option that is native on both platforms without a new systems language in v1.

**Consequences:** constants, skip lists, and redaction regexes live in `packages/engine-policy/policy.json`, not copied by hand. A Python test asserts `constants.py` matches that file so the CLI and the Hosts cannot silently diverge on policy.
