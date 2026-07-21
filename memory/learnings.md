# Agent Learnings

## NEVER run parallel search_replace calls on the SAME file (Jul 21, 2026)
Batched 6 parallel edits to server.py — two edits were silently lost and the file tail
got corrupted (stray `ame__)` + duplicated block → SyntaxError). Tool reported success
for all. Fix: edits to DIFFERENT files can be parallel; multiple edits to ONE file must
be sequential (or combined into a single search_replace). Always re-grep the file for
all expected changes after a parallel batch that touched it.

## Preview DB quirks
- Preview has almost no stamped master_items → item_profit summaries mostly empty;
  verify profit logic with an injected stamped item + cleanup (batch_id marker).
- Safe test dates: use year 2019 (no real data collision).
