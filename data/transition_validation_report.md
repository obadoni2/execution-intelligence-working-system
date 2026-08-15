# SUPT Transition-Specific Validation Report

## Product Question

Does the agent improve execution before CLUTCH becomes obvious, or is it only reacting after composite d_ij crosses 1.0?

## Validation Window

- First block: `19000149`
- Last block: `25015827`
- Block span: `6015678`
- Approx hours at 12s/block: `20052.26`
- CLUTCH transitions found: `8`

## Lead-Time Result

- Pre-divergence rate: `87.50%`
- Pre-agent-shift rate: `87.50%`
- Median gas/channel lead: `18.00` blocks
- Mean gas/channel lead: `15.86` blocks
- P10/P90 gas lead: `11.00` / `19.40` blocks
- Median agent lead: `18.00` blocks

## Execution Savings Across Transition Windows

| Policy | Total cost proxy | SUPT reduction vs policy |
|---|---:|---:|
| Always execute | 340.649081 | 80.56% |
| Reactive CLUTCH-only | 152.291121 | 56.52% |
| Simple gas-threshold | 57.637396 | -14.88% |
| SUPT gradient agent | 66.213368 | baseline |

## Failure Modes

- False EARLY_CAUTION/CAUTION without CLUTCH: `180`
- CLUTCH without prior gas/base-fee divergence: `1`
- CLUTCH without prior agent shift: `1`

## Event Table

|   event_id |   clutch_block |   gas_channel_lead_blocks |   agent_lead_blocks | had_pre_divergence   | had_pre_agent_shift   | at_clutch_agent_state   | at_clutch_agent_mode   | future_bad_after_clutch   |   supt_reduction_vs_reactive |   supt_reduction_vs_gas_threshold |
|-----------:|---------------:|--------------------------:|--------------------:|:---------------------|:----------------------|:------------------------|:-----------------------|:--------------------------|-----------------------------:|----------------------------------:|
|          1 |       24993872 |                       nan |                 nan | False                | False                 | HIGH_STRESS             | PAUSE                  | True                      |                     0        |                         0         |
|          2 |       24994753 |                        18 |                  18 | True                 | True                  | HIGH_STRESS             | PAUSE                  | True                      |                     0.572742 |                        -0.0467022 |
|          3 |       24994763 |                        18 |                  18 | True                 | True                  | HIGH_STRESS             | PAUSE                  | True                      |                     0.549318 |                         0.0247858 |
|          4 |       24994766 |                        16 |                  16 | True                 | True                  | HIGH_STRESS             | PAUSE                  | True                      |                     0.535398 |                         0.0598745 |
|          5 |       24994772 |                        15 |                  19 | True                 | True                  | HIGH_STRESS             | PAUSE                  | True                      |                     0.5      |                         0.131503  |
|          6 |       25014668 |                        20 |                  20 | True                 | True                  | HIGH_STRESS             | PAUSE                  | True                      |                     0.65     |                         0         |
|          7 |       25015442 |                         5 |                   5 | True                 | True                  | HIGH_STRESS             | PAUSE                  | True                      |                     0.25     |                         0.655727  |
|          8 |       25015651 |                        19 |                  15 | True                 | True                  | HIGH_STRESS             | PAUSE                  | True                      |                     0.634122 |                        -8.87573   |

## Guardrail

This is transition-window validation using proxy execution costs, not live PnL. It tests whether gas/channel divergence and near-threshold behavior give the agent a measurable early-decision edge before full CLUTCH confirmation.