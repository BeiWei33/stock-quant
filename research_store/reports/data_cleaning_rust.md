# Data Cleaning Report

## Summary
| Metric | Value |
| --- | --- |
| Input Rows | 5400 |
| Output Rows | 5400 |
| Changed Rows | 864 |
| Auto Fixed Rows | 864 |
| Manual Review Rows | 0 |
| High Fixed | 433 |
| Low Fixed | 431 |
| Non-positive Volume | 0 |
| Non-positive Amount | 0 |

## Rule Counts
| Rule | Count |
| --- | --- |
| ohlc_envelope_high | 433 |
| ohlc_envelope_low | 431 |
| zero_volume | 0 |
| non_positive_price | 0 |
| non_positive_amount | 0 |

## Before/After Samples
| Code | Date | Field | Before | After | Rule | Action |
| --- | --- | --- | --- | --- | --- | --- |
| 000001.SZ | 2024-01-08 | low | 9.761552015150398 | 9.683283855095823 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-01-15 | high | 9.701343308563443 | 9.730438159374197 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-01-23 | high | 9.86281409216268 | 9.863308352634983 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-01-24 | low | 9.515764027282195 | 9.489267356109826 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-01-26 | low | 9.083427601099606 | 9.070255645785204 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-02-06 | low | 8.412486023404133 | 8.397264295047119 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-02-12 | low | 8.010102064886622 | 8.004009533529427 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-02-19 | low | 7.614186046507703 | 7.568543493220625 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-02-21 | high | 7.530278441316313 | 7.530335162461385 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-03-01 | high | 7.431507042772705 | 7.456902653758813 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-03-07 | high | 7.5678087056910766 | 7.580135807823077 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-03-14 | low | 7.626954997878479 | 7.587723703820024 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-03-18 | low | 7.715110941479474 | 7.683375331973334 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-03-29 | low | 7.770902274181845 | 7.756774709876785 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-04-01 | low | 7.690593903510112 | 7.688200744639573 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-04-18 | high | 7.685731844210526 | 7.6873126202280595 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-04-23 | high | 7.770466098072996 | 7.771716325880574 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-05-07 | high | 7.746793638096153 | 7.802325896388522 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-05-31 | high | 7.450220646491785 | 7.482374915654467 | ohlc_envelope | AUTO_FIX |
| 000001.SZ | 2024-06-03 | high | 7.4203153271424735 | 7.420682095675424 | ohlc_envelope | AUTO_FIX |
