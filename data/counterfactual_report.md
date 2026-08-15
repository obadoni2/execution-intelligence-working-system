# SUPT Counterfactual Execution Report

## Product Question

Did the agent avoid bad execution windows compared with a baseline that executes full notional every block?

## Overall

- Evaluated windows: `1519`
- Total baseline bad exposure: `308.000000`
- Total agent bad exposure: `77.250000`
- Total avoided bad exposure: `230.750000`
- Bad execution exposure reduction: `74.92%`
- Total baseline future risk exposure: `990.586891`
- Total agent future risk exposure: `490.246284`
- Total avoided future risk exposure: `500.340606`
- Future risk exposure reduction: `50.51%`

## By Horizon / Agent State

|   horizon_blocks | start_agent_risk_state   | start_agent_execution_mode   |   rows |   future_bad_rate |   avoided_bad_count |   baseline_bad_exposure |   agent_bad_exposure |   avoided_bad_exposure |   baseline_future_risk_exposure |   agent_future_risk_exposure |   avoided_future_risk_exposure |
|-----------------:|:-------------------------|:-----------------------------|-------:|------------------:|--------------------:|------------------------:|---------------------:|-----------------------:|--------------------------------:|-----------------------------:|-------------------------------:|
|                5 | CAUTION                  | REDUCE_SIZE                  |    177 |        0.288136   |                   0 |                      51 |                18.9  |                  32.1  |                        129.705  |                     57.4577  |                       72.2472  |
|                5 | EARLY_CAUTION            | SELECTIVE_EXECUTE            |     23 |        0.0434783  |                   0 |                       1 |                 0.75 |                   0.25 |                         11.5777 |                      8.68327 |                        2.89442 |
|                5 | HIGH_STRESS              | PAUSE                        |     42 |        1          |                  42 |                      42 |                 0    |                  42    |                         49.778  |                      0       |                       49.778   |
|                5 | NORMAL                   | EXECUTE_FULL                 |    117 |        0.00854701 |                   0 |                       1 |                 1    |                   0    |                         53.0308 |                     53.0308  |                        0       |
|                5 | RECOVERY                 | RESUME_GRADUALLY             |    152 |        0.0394737  |                   0 |                       6 |                 3    |                   3    |                         88.2928 |                     44.1464  |                       44.1464  |
|               10 | CAUTION                  | REDUCE_SIZE                  |    172 |        0.27907    |                   0 |                      48 |                18.5  |                  29.5  |                        125.913  |                     56.3157  |                       69.5977  |
|               10 | EARLY_CAUTION            | SELECTIVE_EXECUTE            |     23 |        0.0434783  |                   0 |                       1 |                 0.75 |                   0.25 |                         11.5287 |                      8.64652 |                        2.88217 |
|               10 | HIGH_STRESS              | PAUSE                        |     42 |        1          |                  42 |                      42 |                 0    |                  42    |                         49.9597 |                      0       |                       49.9597  |
|               10 | NORMAL                   | EXECUTE_FULL                 |    117 |        0.00854701 |                   0 |                       1 |                 1    |                   0    |                         53.2708 |                     53.2708  |                        0       |
|               10 | RECOVERY                 | RESUME_GRADUALLY             |    152 |        0.0592105  |                   0 |                       9 |                 4.5  |                   4.5  |                         89.3786 |                     44.6893  |                       44.6893  |
|               20 | CAUTION                  | REDUCE_SIZE                  |    168 |        0.27381    |                   0 |                      46 |                19.1  |                  26.9  |                        123.48   |                     55.8171  |                       67.6629  |
|               20 | EARLY_CAUTION            | SELECTIVE_EXECUTE            |     23 |        0.0434783  |                   0 |                       1 |                 0.75 |                   0.25 |                         11.5418 |                      8.65636 |                        2.88545 |
|               20 | HIGH_STRESS              | PAUSE                        |     42 |        1          |                  42 |                      42 |                 0    |                  42    |                         47.9909 |                      0       |                       47.9909  |
|               20 | NORMAL                   | EXECUTE_FULL                 |    117 |        0.00854701 |                   0 |                       1 |                 1    |                   0    |                         53.926  |                     53.926   |                        0       |
|               20 | RECOVERY                 | RESUME_GRADUALLY             |    152 |        0.105263   |                   0 |                      16 |                 8    |                   8    |                         91.2128 |                     45.6064  |                       45.6064  |

## Guardrail

This is a counterfactual proxy report, not live PnL. It compares the agent branch against a baseline branch using future gas/regime/risk conditions. Real slippage, gas paid, fill price vs mid, and transaction success rate can plug into this same structure later.