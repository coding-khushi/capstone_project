# Percept evaluation summary

Runs: 18 (0 failed with Gemini/network errors and are excluded below).

| Case type | Mode | Runs | Response accuracy | Task completion | Decision correct | Retrieval hit | Mean latency (s) | Mean context tokens | Mean Gemini calls |
|---|---|---|---|---|---|---|---|---|---|
| screen_sufficient | screen_only | 4 | 1.00 | 1.00 | - | - | 16.1 | 1991.25 | 1.00 |
| screen_sufficient | retrieval | 4 | 1.00 | 1.00 | 1.00 | - | 19.4 | 2808.25 | 1.00 |
| needs_retrieval | screen_only | 5 | 0.00 | 0.00 | - | - | 7.7 | 1992.40 | 1.00 |
| needs_retrieval | retrieval | 5 | 1.00 | 1.00 | 1.00 | 1.00 | 21.0 | 8175.20 | 2.60 |
