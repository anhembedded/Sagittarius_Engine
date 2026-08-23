---
name: Documentation Style
description: Markdown structure, writing style, and diagram conventions for project documentation. Load when writing or editing docs. See doc-code-sync.md for the update-with-code obligation — not restated here.
trigger: model_decision
---

# Rules: Documentation

> Context: Universal constraints for structuring, writing, and updating project documentation.

## 1. Structure & Formatting

* **Strict Markdown:** Use standard, clean Markdown syntax.
* **Clear Hierarchy:** Use `#`, `##`, `###` logically to create a scannable outline. Never skip heading levels.
* **Code Blocks:** ALWAYS specify the language for syntax highlighting (e.g., ````typescript`).

## 2. Writing Style

* **Active & Direct:** Use active voice. Be concise and instructional (e.g., "Run the server," not "The server should be run").
* **Value-Driven:** Focus on "Why" and "How-to". Avoid dumping internal implementation details into public-facing guides.
* **Consistent Terminology:** Strictly use official project terms. Do not use synonyms for core concepts.

## 3. Diagrams & Visuals

* **Mermaid Only:** Use Mermaid.js for all diagrams (architecture, sequence, relationships, decision flow). Do not use external image files.
* **NO Screenshots:** Never use screenshots for UI or code (they become outdated quickly and cannot be searched).

## 4. Maintenance & Updates

The full obligation — update docs in the same change as the code, keep every claim
traceable to something real — lives in `doc-code-sync.md`, not here, so it has exactly one
home instead of drifting copies. The short version: **no zombie docs.** If a feature is
deprecated or removed, its documentation goes with it in the same change.
