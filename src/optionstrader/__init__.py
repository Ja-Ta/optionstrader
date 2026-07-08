"""optionstrader — cash-generation engine implementing the strategy in docs/.

Tier 1 modules (see docs/03-implementation-guide.md §6):
  indicators/  — MA/EMA tests, CMF, volume stats, support/resistance detection
  signals/     — per-position decision state machine
  options/     — strike/expiration selector, short-premium tracker
  portfolio/   — cost-basis ledger + mark-to-market
  data/        — pluggable market-data providers (yfinance default)
"""

__version__ = "0.1.0"
