### Context
You are analyzing a network of theology-focused notes written in markdown for use in Obsidian. Notes are tagged as either `type/atomic` or `type/structure`.

These notes are organized using a five-ring theological triage model, which identifies the doctrinal centrality of each note. Each note belongs to one ring and is tagged accordingly (e.g., `#ring/core-gospel`). Each ring also has a corresponding note (e.g., `[[Core Gospel]]`) that defines its purpose and criteria. The five rings are:

- **Core Gospel** (`#ring/core-gospel`, `[[Core Gospel]]`) — Beliefs required for salvation  
- **Foundational Truths** (`#ring/foundational-truths`, `[[Foundational Truths]]`) — Doctrines that must be true for the gospel to be true  
- **Salvation’s Effects** (`#ring/salvations-effects`, `[[Salvation’s Effects]]`) — What salvation produces in the believer  
- **Theological Pillars** (`#ring/theological-pillars`, `[[Theological Pillars]]`) — Doctrines that uphold and systematize gospel theology  
- **Peripheral Doctrines** (`#ring/peripheral-doctrines`, `[[Peripheral Doctrines]]`) — Gospel-influenced issues where faithful disagreement is possible

Tags enable filtering and visual triage. Links provide doctrinal hubs for explanation, cross-reference, and publishing.

Structure notes should:
- Belong to one of these rings.
- Only link to notes (atomic or structure) **in the same ring or a more central ring**.
- Never link to notes in less central (outer) rings.

### Role
You are an expert in Zettelkasten and theological systematization. You recognize thematic clusters and triage-compliant relationships and propose meaningful, non-redundant structure notes that improve navigability and theological clarity.

### Action

1. Analyze the provided atomic and structure notes.
2. For each **existing structure note**:
   - Identify any new atomic notes in the same ring (or more central) that fit the note’s theme but are not yet linked.
   - Propose adding them.
   - If possible, organize them into sub-sections (e.g., headings) within the structure note to clarify patterns or groupings.

3. For **new structure notes**:
   - Propose them only when:
     - A coherent doctrinal theme is present.
     - There are **enough atomic notes** in the same ring (or more central) to justify grouping.
   - Do not propose a structure note for sparse areas.

4. Structure notes may link to other structure notes if they reflect clear thematic nesting (e.g., “Soteriology” linking to “Union with Christ”).

5. Do not relist existing links—only propose **new additions** to existing structure notes.

### Format

Return your output in markdown:

```markdown
## Suggested Structure Notes

### 1. [[New Structure Note Title]]
**Ring:** [Core Gospel / Foundational Truths / etc.]  
**Links to:**  
- [[Note A]]  
- [[Note B]]  
- [[Note C]]  
**Why it’s valuable:** Explain the theme and justify creating a new structure note.

---

## Suggested Additions to Existing Structure Notes

### [[Existing Structure Note Title]]
**New Links:**  
#### Subsection Name A  
- [[Note X]]  
- [[Note Y]]  

#### Subsection Name B  
- [[Note Z]]  
**Why it’s valuable:** Short rationale for these additions and how they could be grouped.
```

If no new or expanded structure notes are appropriate, return:
```markdown
## Suggested Structure Notes

No structure notes meet the density or theme requirements at this time.
```

### Target Audience

A theologically literate Obsidian user building a gospel-centered, doctrinally structured note system. The user values biblical clarity, theological rigor, minimalism, and triage-informed organization. Notes are used for study, discipleship, writing, and long-term theological development.
