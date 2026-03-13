# Vector Search vs Keyword Search: Test Plan

Use this test plan with the `vector_search_test_data.csv` dataset to demonstrate where each search method wins and loses.

## How to Use This

Run each query against the dataset using both keyword search and vector/semantic search. Compare the results. The "Expected Outcome" tells you what should happen.

---

## Part 1: Where Keyword Search Works Fine

These are the easy wins for keyword search. If vector search can't match these, something is misconfigured.

| # | Search Query | Why Keyword Search Works | Expected Result Count (approx) |
|---|---|---|---|
| 1 | `TKT-00042` | Exact ID match. Keyword search was born for this. | 1 |
| 2 | `Salesforce` | Exact app name appears literally in text. | ~180+ |
| 3 | `Finance` | Department name is a literal string match. | ~200+ |
| 4 | `Building A` | Location string appears verbatim. | ~330+ |
| 5 | `error 0x80070005` | Error codes are exact strings. Vector search may actually struggle here because error codes have no semantic meaning. | ~35 |
| 6 | `blue-screen` | Specific technical term used as-is in the data. | ~50+ |
| 7 | `DHCP` | Acronym used literally. Embeddings sometimes fumble acronyms. | ~30+ |
| 8 | `Jordan` | Person name, exact match. | ~100+ |
| 9 | `550 5.1.1` | SMTP error code. Pure string matching territory. | ~50+ |
| 10 | `.NET 6.0` | Version string. No semantic content, just characters. | ~25+ |

**Key point:** These work because the search term appears literally in the data. No understanding required, just pattern matching.

---

## Part 2: Where Keyword Search Fails and Vector Search Should Win

These queries describe a *concept* but use words that don't appear in the matching tickets. This is where you prove the value.

| # | Search Query | What It Should Find | Why Keyword Search Fails |
|---|---|---|---|
| 1 | `employee can't log in` | All ~900 password/credential/auth tickets | Most tickets say "credentials," "access," "authentication," "sign-in," "locked out," or "secret phrase" instead of "log in" |
| 2 | `broken computer` | All ~600 hardware tickets | Tickets say "won't turn on," "screen flickering," "buzzing noise," "hinge is broken," "blue-screens" instead of "broken computer" |
| 3 | `need new program` | All ~700 software install tickets | Tickets say "app deployment," "tool onboarding," "application provisioning," "package install" instead of "new program" |
| 4 | `internet not working` | All ~650 network tickets | Tickets say "connectivity drops," "DNS not resolving," "limited connectivity," "LAN trouble," "timeout error" |
| 5 | `people can't open files they should have access to` | All ~400 permission tickets | Tickets use "access denied," "entitlements," "role assignment," "security clearance," "authorization" |
| 6 | `someone deleted important documents` | All ~200 data loss tickets | Tickets say "accidental deletion," "file recovery," "content gone," "restore request" |
| 7 | `my machine is really slow` | All ~200 performance tickets | Tickets say "resource bottleneck," "system drag," "thermal throttling," "lag problem" |
| 8 | `working from home connection issues` | All ~250 VPN tickets | Tickets say "tunnel connection," "secure gateway," "remote access," "off-site link" |
| 9 | `phone setup for work` | All ~130 mobile tickets | Tickets say "handheld device," "cell configuration," "portable tech," "smartphone issue" |
| 10 | `video call problems` | All ~100 meeting tech tickets | Tickets say "conference room AV," "collaboration tools," "presentation tech," "video call setup" |
| 11 | `help, I'm locked out of everything` | Password + Permission tickets (~1300) | Concept spans two categories. Keyword hits neither well because "locked out" is only one of 20+ phrasings. |
| 12 | `user returned from vacation and nothing works` | Password reset + VPN + software tickets | Cross-category concept. Multiple ticket types describe post-leave access issues with different words. |
| 13 | `device overheating` | Hardware (thermal) + Performance (throttling) tickets | "Overheating" appears rarely. Related tickets say "95°C," "thermal paste," "fans spin up," "thermal throttles" |
| 14 | `company app won't start` | Software install (crash) + Performance (slow launch) tickets | "Won't start" maps to "crashes immediately," "fails with error," "hangs at 90%," "splash screen then closes" |
| 15 | `security concern with someone's account` | Password (compromised) + Permission (unauthorized access) tickets | "Security concern" is never used literally. Related tickets say "suspects someone else tried," "still has active access," "sees other people's data" |

---

## Part 3: Tricky Queries That Expose Keyword Search Weaknesses

These are realistic user queries where keyword search returns either nothing useful or too much noise.

### 3a: High Noise (keyword returns wrong results)

| # | Search Query | The Problem |
|---|---|---|
| 1 | `access` | Matches password tickets, permission tickets, VPN tickets, and even some software install tickets. Keyword search can't tell which kind of "access" you mean. Vector search can use the surrounding context. |
| 2 | `not working` | Matches almost everything. Keyword search gives you 2000+ results with no ranking by relevance. Vector search understands what "not working" means differently for a printer vs a VPN. |
| 3 | `connection` | Matches network, VPN, docking station, Bluetooth, and email (SMTP connection). Five different problem domains, all using the same word. |
| 4 | `update` | Matches firmware updates (hardware), app updates (software), OS updates (performance), BIOS updates (hardware), security updates (password). Keyword search can't disambiguate. |
| 5 | `can't open` | Matches "can't open attachments" (email), "can't open the shared folder" (permissions), "can't open documents" (software), "screen doesn't stay open" (hardware). Totally different problems. |

### 3b: Zero Results (keyword finds nothing)

| # | Search Query | Why It Returns Nothing |
|---|---|---|
| 1 | `credentials expired` | The dataset uses "password expired" or "certificate expired" but never "credentials expired" together. |
| 2 | `tech support for remote workers` | Nobody writes tickets this way, but it perfectly describes VPN + mobile + performance-from-home tickets. |
| 3 | `machine making weird sounds` | Tickets say "buzzing noise," "grinding noise," "fans spin up." The word "weird" and "sounds" don't appear. |
| 4 | `apps keep closing on their own` | Tickets say "crashes immediately," "freezes and eventually crashes," "closes after splash screen." Same concept, zero word overlap. |
| 5 | `can't do my job because of IT problems` | This is what every ticket *means*, but no ticket *says* it. Vector search should rank high-impact, workflow-blocking tickets. |

---

## Scoring Your Results

For each query in Part 2, measure:

- **Keyword Recall**: Of all relevant tickets, what % did keyword search find?
- **Vector Recall**: Of all relevant tickets, what % did vector search find?
- **Precision**: Of the results returned, what % were actually relevant?

The expected pattern:
- Part 1: Keyword ≈ Vector (both good, keyword might be slightly faster)
- Part 2: Keyword recall < 30%, Vector recall > 70%
- Part 3a: Keyword precision < 20% (too much noise), Vector precision > 60%
- Part 3b: Keyword recall = 0%, Vector recall > 50%

---

## The Business Case Summary

After running the tests, your story should be:

1. **Keyword search works great for exact lookups** (ticket IDs, error codes, names, specific app names). Nobody is saying to remove it.
2. **Keyword search fails when users describe problems in their own words**, which is how most people actually search. They don't know the "right" terminology.
3. **Vector search fills the gap** by understanding meaning, not just matching characters. It handles synonyms, paraphrasing, and cross-category concepts.
4. **The ideal setup is hybrid**: keyword for exact matches, vector for everything else.
