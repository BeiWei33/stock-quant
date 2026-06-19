# Rust Risk Guard Report

## Summary
| Metric | Value |
| --- | --- |
| Allowed | false |
| Input Orders | 3 |
| Accepted Orders | 0 |
| Rejected Orders | 3 |
| Total Buy Weight | 0.3000 |

## Policy
| Rule | Value |
| --- | --- |
| Trade Mode | SELL_ONLY |
| Max Order Amount | 100000.00 |
| Max Single Weight | 0.1000 |
| Max Total Buy Weight | 0.9500 |
| Max Daily Loss | 0.0500 |
| Daily Loss | 0.0000 |
| Trading Window | 09:30-15:00 |
| Now | 14:30 |

## Rejections
| Order | Code | Side | Rule | Reason |
| --- | --- | --- | --- | --- |
| paper:momentum_rank:2024-09-09:000002.SZ:BUY | 000002.SZ | BUY | trade_mode_sell_only | trade mode SELL_ONLY rejects buy orders |
| paper:momentum_rank:2024-09-09:000008.SZ:BUY | 000008.SZ | BUY | trade_mode_sell_only | trade mode SELL_ONLY rejects buy orders |
| paper:momentum_rank:2024-09-09:000012.SZ:BUY | 000012.SZ | BUY | trade_mode_sell_only | trade mode SELL_ONLY rejects buy orders |
