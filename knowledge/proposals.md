# Proposed strategy changes

Nothing here is live. The agent never applies a proposal itself. A proposal becomes eligible only after all four gates, in order:

1. Historical test on broker data, rule written down before looking at results.
2. Out-of-sample confirmation on dates not used in step 1.
3. Paper tracking: at least 20 paper decisions or 4 weeks, recorded as `kind: paper` in `decisions.jsonl`.
4. The owner approves it in chat and changes the scheduled prompts.

Format per proposal: id, date, what would change, evidence for each gate, risks, status (`draft`, `testing`, `paper`, `awaiting owner`, `approved`, `rejected`).

## Open proposals

None.
