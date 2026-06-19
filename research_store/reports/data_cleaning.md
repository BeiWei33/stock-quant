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
| 000013.SZ | 2024-01-02 | high | 10.01156920779233 | 10.045096459824045 | ohlc_envelope | AUTO_FIX |
| 000020.SZ | 2024-01-02 | high | 9.863589936876744 | 9.868363105430712 | ohlc_envelope | AUTO_FIX |
| 000021.SZ | 2024-01-02 | high | 10.202649554631144 | 10.21573011696229 | ohlc_envelope | AUTO_FIX |
| 000007.SZ | 2024-01-03 | high | 9.893198277910304 | 9.940201226684094 | ohlc_envelope | AUTO_FIX |
| 000009.SZ | 2024-01-03 | high | 10.361409911173176 | 10.376912712589773 | ohlc_envelope | AUTO_FIX |
| 000015.SZ | 2024-01-03 | high | 10.202047360521078 | 10.221282732244472 | ohlc_envelope | AUTO_FIX |
| 000024.SZ | 2024-01-03 | high | 9.98159351924595 | 10.054653703754967 | ohlc_envelope | AUTO_FIX |
| 000006.SZ | 2024-01-04 | high | 10.16105166022948 | 10.173743979077551 | ohlc_envelope | AUTO_FIX |
| 000016.SZ | 2024-01-04 | high | 9.634814334999628 | 9.635261131632165 | ohlc_envelope | AUTO_FIX |
| 000022.SZ | 2024-01-04 | high | 9.821107443516995 | 9.873632682089266 | ohlc_envelope | AUTO_FIX |
| 000003.SZ | 2024-01-05 | high | 9.34759360212321 | 9.350504450490943 | ohlc_envelope | AUTO_FIX |
| 000017.SZ | 2024-01-05 | high | 10.056456607288352 | 10.075210753145791 | ohlc_envelope | AUTO_FIX |
| 000027.SZ | 2024-01-05 | high | 9.951240677754852 | 9.995340991376576 | ohlc_envelope | AUTO_FIX |
| 000007.SZ | 2024-01-08 | high | 9.72556357687652 | 9.728722508531188 | ohlc_envelope | AUTO_FIX |
| 000008.SZ | 2024-01-08 | high | 10.01822515882692 | 10.107100798208617 | ohlc_envelope | AUTO_FIX |
| 000020.SZ | 2024-01-08 | high | 9.679977929284853 | 9.684650522257304 | ohlc_envelope | AUTO_FIX |
| 000006.SZ | 2024-01-09 | high | 9.41770654591072 | 9.467383420603376 | ohlc_envelope | AUTO_FIX |
| 000004.SZ | 2024-01-10 | high | 11.079717400981831 | 11.18532570581258 | ohlc_envelope | AUTO_FIX |
| 000009.SZ | 2024-01-10 | high | 9.94241320274955 | 9.951580555132669 | ohlc_envelope | AUTO_FIX |
| 000014.SZ | 2024-01-10 | high | 10.244717503338885 | 10.323852375273644 | ohlc_envelope | AUTO_FIX |
