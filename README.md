# Do The Crime ⚖️ / 關多久？

Two real U.S. federal cases side by side: **who got more prison time?**
Keep guessing right to build a streak. No names, no faces — only the crime and the time.

Play: https://liyun-li.github.io/do-the-crime/

- Data: U.S. Department of Justice press releases (public domain), sentencing announcements only (post-conviction).
- Excluded: sex crimes, crimes against children, homicides/deaths, kidnapping, shootings, domestic/partner violence, hate crimes, terrorism, immigration, serious-injury assaults; multi-defendant releases; defendant and victim names.
- Curated pool: the game plays only `curated.json`, a hand-picked, hand-verified set built from `curate/picks.tsv` in the source repo (each line checked against its DOJ release).
- Zero load on justice.gov: players only download the static `curated.json`. A daily GitHub Action (`.github/workflows/refresh.yml`) makes at most 12 spaced-out requests to the DOJ API, stops at already-known releases, and writes new auto-parsed cases to `tools/review_queue.json` for human review. Nothing from the queue is played until promoted by hand.
- One-liners are rewritten to be short and funny, drafted with an AI assistant and checked line by line against each release (facts from DOJ, wording ours; jokes target the crime, never identity). English and 中文 play the same pool; the Daily chain is the same for everyone.
- Not affiliated with or endorsed by the DOJ. Always trust the linked release over the card.
