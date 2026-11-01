# Do The Crime ⚖️ / 關多久？

Two real U.S. federal cases side by side: **who got more prison time?**
Keep guessing right to build a streak. No names, no faces — only the crime and the time.

Play: https://liyun-li.github.io/do-the-crime/

- Data: U.S. Department of Justice press releases (public domain), sentencing announcements only (post-conviction).
- Excluded: sex crimes, crimes against children, homicides/deaths, kidnapping, shootings, domestic/partner violence, hate crimes, terrorism, immigration, serious-injury assaults; multi-defendant releases; defendant and victim names.
- Zero load on justice.gov: players only download the static `cases.json`. A daily GitHub Action (`.github/workflows/refresh.yml`) makes at most 12 spaced-out requests to the DOJ API, stops at already-known releases, and commits only on change.
- One-liners are cut from DOJ headlines (no LLM). Chinese lines are hand-translated, so 中文 mode and the Daily chain use the translated subset.
- Not affiliated with or endorsed by the DOJ. Always trust the linked release over the card.
