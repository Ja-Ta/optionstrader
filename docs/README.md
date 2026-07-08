# Working Documents — Elias Cash-Generation Strategy

Deep-dive analysis of `options-trading-strategy.md` (Samir Elias, *Generate Thousands in Cash on Your Stocks Before Buying or Selling Them*, 3rd rev. ed., 2007). These documents distill the book's complete system into working material for building an options trading application.

| Document | Purpose |
|---|---|
| [01-strategy-overview.md](01-strategy-overview.md) | What the strategy actually is — the core engine and its supporting layers, explained end to end |
| [02-why-it-works.md](02-why-it-works.md) | The author's rationale for why it's successful, plus an independent critical assessment of which claims hold up |
| [03-implementation-guide.md](03-implementation-guide.md) | How to realistically implement it today — workflow, portfolio structure, modern-market adaptations, and what an application must automate |
| [04-key-rules-reference.md](04-key-rules-reference.md) | The consolidated rulebook — every numeric threshold, formula, signal, and decision rule in the book |
| [05-success-metrics.md](05-success-metrics.md) | How the book defines and measures success, and what realistic targets look like |
| [06-screening-module.md](06-screening-module.md) | **Extension (not from the book):** modified 20/20/20 capability screen for selecting long-term account candidates — fills the book's selection gap; all trading rules remain the book's |

## One-paragraph summary

The book's core thesis: a stock you own (or want to own) is like a rental property — its *time value* can be rented out continuously. The engine is systematic **covered-call selling at chart resistance** and **cash-secured put selling at chart support**, harvested aggressively (buy back any short option once 75% of its premium is captured, then re-sell), with strikes and timing dictated by a small set of technical signals (moving-average crossovers, Chaikin Money Flow, momentum-fade signals). Around this engine sit an entry method (get paid to buy via put selling), a defense method (roll calls down a falling stock to cut cost basis), an exit-timing method (weekly relative-strength "CD" charts), and a handful of episodic special plays (short squeezes, earnings squeezes, expiration fades). Success is measured in **cash generated per month against capital** and in **driving cost basis toward zero**, not in picking winners.

## Source coverage

All 20 chapters plus introduction and epilogue of the ~9,800-line source file were read and extracted (five parallel full-text passes). OCR defects in the source were flagged and resolved during extraction; the handful of genuinely ambiguous numbers are noted inline in the reference doc.
