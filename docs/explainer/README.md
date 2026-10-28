# Project explainer page (backup copy)

Published as a private Claude artifact: https://claude.ai/artifact/3oss3vmvpt3f4kwbmHETp2
(open it and use Share to give someone access).

- `index.html` - the published page as built (CSS, SVG diagrams, cost explorer script and its
  data all inline). It loads five figures from `img/`, which are copies of:
  - `reports/multicity/fig_cost_regret.png`, `fig_forest_clean.png`, `fig_pareto_clean.png`,
    `fig_rolling_bike_unmodified.png`, `fig_rolling_city_chicago_unmodified.png`.
- `costdata.json` - the per-stream cost terms the interactive κ explorer uses (from
  `amm cost-model`, `reports/multicity/costmodel.csv`). The page already inlines this file.

To change the page in a later session: read the artifact back (the Claude Artifact tool,
`read` on the URL above), edit that copy, and republish to the same URL so the link stays the
same. This folder is only a fallback in case the artifact is lost.

Sections: problem, MAPE-K framework, timing / information boundary, state machine and gates,
triggers, probe, data (NYC 2018 bug), protocol, results, failure analysis (reference
inflation), cost model, related work, design decisions, limits, how to reproduce, and 36
autonomous-systems viva questions with answers.
