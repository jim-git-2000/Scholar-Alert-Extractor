---
name: filter-doa-array-papers
description: >-
  Incrementally screen newly appended records in an existing Scholar Alert Extractor
  output/papers.xlsx and append only papers genuinely related to direction-of-arrival estimation or
  array signal processing to a separate filtered Excel workbook. Use when the user asks to screen
  new papers since the previous run, update the DOA/array shortlist, or inspect incremental
  filtering status. Never fetch or process email.
---

# Filter DOA and Array Papers

Read the existing source workbook only. Use Codex reasoning for semantic classification and the
bundled helper for deterministic checkpoint and Excel operations.

## Fixed paths

Use these defaults unless the user explicitly overrides them:

```bash
project_dir="/workspace/other-projects/Scholar Alert Extractor"
venv_dir="$HOME/.venvs/scholar-alert-extractor"
skill_dir="${CODEX_HOME:-$HOME/.codex}/skills/filter-doa-array-papers"
source_file="$project_dir/output/papers.xlsx"
state_file="$project_dir/output/.doa_array_filter_state.json"
pending_file="$project_dir/output/.doa_array_pending.json"
decisions_file="$project_dir/output/.doa_array_decisions.json"
filtered_file="$project_dir/output/doa_array_papers.xlsx"
```

Do not call `scholar process`, access IMAP, change email flags, or rely on a Bash function.

## Incremental workflow

1. Read [references/relevance-rubric.md](references/relevance-rubric.md) completely before making
   decisions.
2. Prepare at most 30 source rows appended after the durable checkpoint:

   ```bash
   "$venv_dir/bin/python" "$skill_dir/scripts/filter_papers.py" prepare \
     --source "$source_file" --state "$state_file" --pending "$pending_file" \
     --decisions "$decisions_file" --output "$filtered_file" --limit 30
   ```

3. If `new_in_batch` is zero, stop. The filtered workbook is already current.
4. Read the complete pending JSON. Fill every null field in the generated decisions JSON using
   `apply_patch`; retain every `id`, `fingerprint`, and the top-level `batch_token` exactly.
5. Classify semantically. Never treat a keyword match alone as evidence. Use the title, snippet,
   publication, and alert context together. When metadata is insufficient, use `review` instead of
   guessing.
6. Use only the metadata already present in the Excel record. Do not browse paper pages or fetch
   additional metadata. Keep genuinely under-specified records as `review`.
7. Apply the complete batch:

   ```bash
   "$venv_dir/bin/python" "$skill_dir/scripts/filter_papers.py" apply \
     --pending "$pending_file" --decisions "$decisions_file"
   ```

8. Repeat prepare, classify, and apply until `new_in_batch` is zero.
9. Report this run's number of newly inspected and newly appended papers, cumulative relevant,
   excluded, and review counts, and link `output/doa_array_papers.xlsx`. List review titles in the
   report; review records are checkpointed but are not added to the filtered workbook.

The first run treats every existing source record as new. Later runs consider only source rows after
`last_source_row`; changes to already-screened rows do not trigger reclassification.

## Decision contract

Set `decision` to exactly one of:

- `relevant`: the primary technical contribution is in scope; append it to filtered `Papers`.
- `review`: available evidence cannot support a reliable result; checkpoint but do not append it.
- `excluded`: the primary contribution is out of scope; checkpoint but do not append it.

Set `scope` to one of `core-doa`, `array-signal-processing`, `array-design-calibration`,
`joint-spatial-estimation`, `borderline`, or `out-of-scope`. Use `borderline` only with `review` and
`out-of-scope` only with `excluded`.

Write a concise, paper-specific Chinese `reason`. Populate `matched_topics` with specific concepts,
not generic terms such as “signal” or “method”. Set `evidence_basis` to one of `title`,
`title-and-snippet`, or `metadata-insufficient`.

## Integrity and recovery

- Never modify `output/papers.xlsx`; it is the source of truth.
- Append only `relevant` records to the filtered workbook's `Papers` sheet. Never add excluded or
  review records there.
- Treat `.doa_array_filter_state.json` as the durable checkpoint. Never hand-edit it.
- The helper verifies that source rows before the checkpoint were not deleted, renamed, or reordered.
  If this check fails, stop and ask the user whether to reset and rescreen everything.
- The helper validates source snapshots, batch tokens, fingerprints, and complete decision coverage
  before updating files.
- If the source workbook changes after prepare, rerun prepare and classify the regenerated batch.
- If the filtered workbook is open and replacement fails, ask the user to close it and rerun apply.
  The checkpoint advances only after the filtered workbook is saved successfully.
- Use `reset` only after explicit user approval. It archives the checkpoint rather than deleting it;
  the filtered workbook remains intact and prevents duplicate `dedup_key` appends.

## Status and explicit reset

Inspect counts without changing files:

```bash
"$venv_dir/bin/python" "$skill_dir/scripts/filter_papers.py" status \
  --source "$source_file" --state "$state_file"
```

After explicit approval, reset the incremental checkpoint for a complete rescreen:

```bash
"$venv_dir/bin/python" "$skill_dir/scripts/filter_papers.py" reset --state "$state_file"
```
