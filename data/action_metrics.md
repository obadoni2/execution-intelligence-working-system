# Gradient Execution Per-Action Metrics

## Product Question

Which agent actions are actually improving future execution-risk outcomes against the baseline?

- Horizon: `10` blocks

## Per-Action Summary

| risk_state    | execution_mode    |   rows |   future_bad_rate |   avoided_bad_count |   baseline_bad_exposure |   agent_bad_exposure |   avoided_bad_exposure |   bad_exposure_reduction |   baseline_future_risk_exposure |   agent_future_risk_exposure |   avoided_future_risk_exposure |   future_risk_reduction |   mean_future_risk_score |   mean_future_gas_dij |   mean_future_base_fee_dij |
|:--------------|:------------------|-------:|------------------:|--------------------:|------------------------:|---------------------:|-----------------------:|-------------------------:|--------------------------------:|-----------------------------:|-------------------------------:|------------------------:|-------------------------:|----------------------:|---------------------------:|
| HIGH_STRESS   | PAUSE             |     42 |        1          |                  42 |                      42 |                 0    |                  42    |                 1        |                         49.9597 |                      0       |                       49.9597  |                1        |                 1.18952  |             1.14893   |                  0.836324  |
| CAUTION       | REDUCE_SIZE       |    172 |        0.27907    |                   0 |                      48 |                18.5  |                  29.5  |                 0.614583 |                        125.913  |                     56.3157  |                       69.5977  |                0.552743 |                 0.732055 |             0.46876   |                  0.374095  |
| RECOVERY      | RESUME_GRADUALLY  |    152 |        0.0592105  |                   0 |                       9 |                 4.5  |                   4.5  |                 0.5      |                         89.3786 |                     44.6893  |                       44.6893  |                0.5      |                 0.588017 |             0.243988  |                  0.18864   |
| EARLY_CAUTION | SELECTIVE_EXECUTE |     23 |        0.0434783  |                   0 |                       1 |                 0.75 |                   0.25 |                 0.25     |                         11.5287 |                      8.64652 |                        2.88217 |                0.25     |                 0.501247 |             0.0490709 |                  0.035088  |
| NORMAL        | EXECUTE_FULL      |    117 |        0.00854701 |                   0 |                       1 |                 1    |                   0    |                 0        |                         53.2708 |                     53.2708  |                        0       |                0        |                 0.455306 |             0.0162643 |                  0.0117165 |

## Interpretation

HIGH_STRESS / PAUSE should show high future bad-rate and high avoided exposure. EARLY_CAUTION and CAUTION should show whether reducing size before full stress improves outcomes. RECOVERY should show whether gradual resume is safe. NORMAL should ideally have low future bad-rate.

## Guardrail

This is still proxy-based counterfactual evaluation, not live PnL. Real execution metrics can later be added: gas paid, slippage, fill price vs mid, confirmation delay, and transaction success rate.