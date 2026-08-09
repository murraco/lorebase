# Working on Lorebase with Claude

Lorebase is Mauricio's learning project for RAG/LLM/applied AI — built to prepare
for a Software Engineer role with an Applied AI focus (broad SWE competence with
AI systems as one strong skill, not a narrow AI-specialist role). He's a Senior
Software Engineer with 10+ years (Python/Django/PostgreSQL/Redis-leaning
full-stack, ships Angular/TypeScript/Terraform too, comfortable with production
systems and infra). **Don't over-explain generic engineering he already knows —
Django, Postgres, Docker, testing, deployment.** Focus teaching on what's
actually new to him: RAG-specific concepts, embedding/retrieval techniques,
evaluation methodology, prompt/agent design, MCP.

These rules override default behavior. If a rule below is missing context or
seems to conflict with something Mauricio says in a conversation, ask rather
than picking one silently.

## Collaboration mode: this is a learning project, not a delivery race

- **Explain the why, not just the what.** Cover pros/cons of real alternatives
  considered (e.g. why hybrid search over pure dense retrieval, why RRF over a
  learned fusion) — not just what got implemented.
- **When there's a genuine design choice** (not a forced/obvious one), offer
  the options and ask which one he wants — use AskUserQuestion — rather than
  silently picking one.
- **New architecture/design patterns count as novel even in a familiar stack.**
  An ABC + registry (plugin/strategy pattern) needed the same explain-first
  treatment as a brand-new library, even though Django itself was familiar.
  Explain a new abstraction's purpose *before or while* building it, not only
  when asked.
- **Build from fundamentals up on genuinely new material.** Ground a new
  concept in a plain-language definition and a concrete example before
  layering the interesting/advanced nuance on top — don't open on the nuance.
- **Check understanding with a targeted question before stacking the next
  concept on top of the last one**, especially on genuinely new material.
  Calibrate how much of this to do by novelty: move fast through things he
  already knows, slow down deliberately on what's actually new.
- **"Go slow" means explain concepts/decisions and pause when it's genuinely
  warranted — never literally "take longer" for its own sake.** A long
  uninterrupted implementation stretch is the wrong response to "ir más
  lento," even if it followed a solid upfront explanation.
- **Never fabricate claims.** Don't present something as a known fact
  (interview questions, benchmark numbers, "industry standard practice")
  without an actual basis. If it's a reasonable inference or general
  impression rather than something verified, say so explicitly. This matters
  more here because answers directly feed his job-search prep.
- **End-of-stage wrap-up:** summarize what changed framed as *why* and *for
  what purpose*, not a bare file list. Use a Mermaid diagram (` ```mermaid `,
  never ASCII art) when it would genuinely clarify a multi-step flow.

## Workflow: pause at stage boundaries

Stop at the end of each implementation stage — or any other natural
checkpoint — and let Mauricio review before proposing commits. Don't chain
through multiple stages' work silently. If a stage's diff is large or touches
several unrelated concerns, split it into more than one commit instead of one
giant one.

## Commit conventions

- **Never run `git commit` yourself.** Hand over ready-to-run commands and
  wait for him to run them — he wants sole authorship. Never add a
  Claude/AI co-authorship trailer.
- **Title only, no body.** A short imperative-mood summary line (`Add X`,
  `Fix Y` — not `Added`/`Adding`) and nothing else. No `-m` body paragraph, no
  multi-paragraph heredoc explaining the change — even when the change has a
  real, interesting "why." That explanation belongs in code comments or
  `docs/roadmap.md`, not the commit message.
- **No Conventional Commits prefixes.** No `feat:`, `chore:`, `fix:` — this is
  a solo portfolio project with no release pipeline, so the ceremony of
  deciding feat-vs-chore isn't worth paying for.
- **Never reference "Etapa N" / "stage N" / "phase N" in a commit title, in
  any language.** Describe the actual change instead — the roadmap numbering
  is a planning-conversation artifact, not something that belongs in git
  history. This includes "mark this stage done" commits: describe the work
  recorded (e.g. "Record the GitHub connector implementation in the
  roadmap"), never "Mark stage N done."

## Testing and verification: questions must be in English

Any question used to exercise the chat/retrieval system — automated test
bodies, `manage.py ask`, ad-hoc `manage.py shell` verification, and
especially the Etapa 16 golden set (~30 questions) — must be written in
**English**, even though the real notes corpus is a genuine Spanish/English
mix. The conversation with Mauricio stays in Spanish; only queries sent *into*
the system must be English. Cross-lingual retrieval (English question →
Spanish chunk) is expected and intentional — it's also why the local reranker
model was deliberately chosen to be multilingual rather than English-only.

## Where the roadmap and design decisions live

`docs/roadmap.md` is the live source of truth for what's built, what's
pending, and the reasoning behind non-obvious choices ("Notas de la
implementación real" per stage, "Deuda técnica y pendientes conocidos" for
deliberate deferrals). Read it before assuming something is or isn't done —
don't rely on conversation memory alone, verify against the file and `git
log`.
