# Domain Docs

This repository uses a single-context domain layout.

Before exploring or changing the code:

- Read root `CONTEXT.md` when present.
- Read relevant decisions under `docs/adr/`.
- Proceed silently when these files do not exist.
- Use canonical terms from the `CONTEXT.md` glossary.
- Surface conflicts with existing ADRs instead of silently overriding them.

Expected structure:

```text
/
|-- CONTEXT.md
|-- docs/
|   |-- agents/
|   `-- adr/
`-- src/
```
