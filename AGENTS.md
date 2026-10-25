# Wing engineering workflow

Repository: wcc118/openfoam. Pass --repo wcc118/openfoam to gh commands;
for repo subcommands that reject it, use the explicit OWNER/REPO positional argument.

## Engineering ownership

The owner requires detailed analysis components to work and be checked before
building the automated configuration/optimization loop. This is an engineering
understanding tool, not an oracle for an exact answer or flight clearance.

Before adding a subsystem, consult docs/REUSE_INVENTORY.md and inspect relevant
existing projects. Pin reused sources and preserve their units, provenance,
validity bounds, licenses, and known limitations. Do not modify sibling repositories
as a side effect. Do not use arbitrary sys.path injection into mutable worktrees.

Keep SI solver inputs with explicit conversions at boundaries. Define axes,
reference area/length, moment origin, pressure meaning, and sign conventions.
Never equate solver exit, numerical verification, physical validation, or flight
capability. Never label a failed solve as a favorable optimization result.
Do not infer flutter from steady angle-of-attack sweeps.

## Issue-driven work

- Start from GitHub issue/PR/head, not a prior conversation alone.
- Verify status/backlog, status/in-progress, status/review, status/review-passed,
  status/blocked, status/done before applying them. At most two unrelated issues active.
- Primary Codex owns architecture, cross-repository interfaces, significant dependencies,
  security, ambiguity, engineering interpretation, and final judgment.
- For bounded ordinary implementation use codex-local-coder REPOSITORY_PATH --task-file FILE
  on an explicit issue branch, never main. Workers do not orchestrate or delegate.
- After a PR exists use codex-local-reviewer REPOSITORY_PATH --task-file FILE;
  provide issue, PR, criteria, and verification evidence, not the coder conversation.
- Coder and reviewer are sequential; reviewer never edits code or merges.
- Approval by a reviewer does not grant merge authorization. No blanket merge
  delegation from another repository applies here.
- Preserve CODEX_THREAD_ID. Issue-bound workers require CODEX_LOCAL_RECORD_RUN=1,
  CODEX_LOCAL_REPOSITORY=wcc118/openfoam, and CODEX_LOCAL_ISSUE=N.
- Retain execution handles until the full harness command exits. Resume yielded
  functions.exec with functions.wait and exec sessions with write_stdin (30 s).
  If lost, use codex-local-completion status --wait 30 until terminal.
  Inspect logs and GitHub head/result, then acknowledge the run with
  codex-local-completion ack RUN_ID --disposition 'observed outcome and next action'.
  Acknowledge failures too; never blindly repeat publication.

## Shared knowledge and artifacts

Read /home/connellwc83/projects/memory/MEMORY.md and search relevant memory before
substantial investigation. Record reusable sourced findings afterward. Memory is
reference material; GitHub is authoritative for work state. Do not retain secrets,
credential-bearing remotes, raw private transcripts, or large result files in Git.
Do not add an open-source license for owner code without an explicit choice.
