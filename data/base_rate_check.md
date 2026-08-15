# Base-Rate Sanity Check + Episode Demo Cards

## Why this matters

This checks whether the agent is truly discriminating risk, not just pausing so often that it catches bad windows by default.

## 2×2 Truth Table

| Agent decision | Future bad | Future good |
|---|---:|---:|
| PAUSE | 42 | 0 |
| EXECUTE / REDUCE / RESUME | 59 | 405 |

## Metrics

- Total windows: `506`
- Pause rate: `8.30%`
- Execute rate: `91.70%`
- Bad rate when paused: `100.00%`
- Bad rate when executed: `12.72%`
- Discrimination gap: `87.28%`
- Agent binary accuracy: `88.34%`
- Bad-window recall: `41.58%`
- Unnecessary pause rate: `0.00%`
- Verdict: `strong_discrimination`

## Episode-Level Demo Cards

### Case 1: HIGH_STRESS → PAUSE

- Episode key: `episode_1`
- Start block: `24993872`
- Future block: `24993891`
- Horizon: `10` blocks
- Agent action: `PAUSE`
- Baseline action: `EXECUTE_FULL`
- Future gas d_ij: `1.2840`
- Future execution risk: `1.3910`
- Avoided bad exposure: `1.000000`
- Avoided future risk exposure: `1.390951`

**Plain-English read:** At block 24993872, the agent classified Ethereum as HIGH_STRESS and chose PAUSE. The baseline would have executed full notional. 10 blocks later, the future window was still bad (future risk=1.3910, gas d_ij=1.2840). The agent avoided that bad execution window.

### Case 2: HIGH_STRESS → PAUSE

- Episode key: `episode_2`
- Start block: `24994773`
- Future block: `24994784`
- Horizon: `10` blocks
- Agent action: `PAUSE`
- Baseline action: `EXECUTE_FULL`
- Future gas d_ij: `1.0430`
- Future execution risk: `1.2441`
- Avoided bad exposure: `1.000000`
- Avoided future risk exposure: `1.244115`

**Plain-English read:** At block 24994773, the agent classified Ethereum as HIGH_STRESS and chose PAUSE. The baseline would have executed full notional. 10 blocks later, the future window was still bad (future risk=1.2441, gas d_ij=1.0430). The agent avoided that bad execution window.

## Guardrail

This is still proxy-based counterfactual evaluation, not live PnL. The purpose is to verify whether the agent makes useful time-varying decisions before showing avoided-window examples externally.