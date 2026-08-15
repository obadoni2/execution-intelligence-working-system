# Example Avoided Execution Windows

## Product Question

Can we show concrete examples where the agent paused and avoided a bad execution window that the baseline would have entered?

## Summary

- Horizon used: `10` blocks
- Examples shown: `9`
- Total avoided bad exposure in examples: `9.000000`
- Total avoided future risk exposure in examples: `12.303329`

## Quick User-Facing Examples

### Example 1

- Start block: `24993872`
- Future block: `24993891`
- Agent state: `HIGH_STRESS`
- Agent action: `PAUSE`
- Start gas d_ij: `1.2613`
- Future gas d_ij: `1.2840`
- Future execution risk: `1.3910`
- Avoided bad exposure: `1.000000`
- Avoided future risk exposure: `1.390951`

**Plain-English read:** At block 24993872, the agent classified the network as HIGH_STRESS and chose PAUSE. 10 blocks later, the future window was still risky (future risk=1.3910, gas d_ij=1.2840). The baseline would have executed into that window, while the agent avoided it.

### Example 2

- Start block: `24993873`
- Future block: `24993891`
- Agent state: `HIGH_STRESS`
- Agent action: `PAUSE`
- Start gas d_ij: `1.2602`
- Future gas d_ij: `1.2840`
- Future execution risk: `1.3910`
- Avoided bad exposure: `1.000000`
- Avoided future risk exposure: `1.390951`

**Plain-English read:** At block 24993873, the agent classified the network as HIGH_STRESS and chose PAUSE. 10 blocks later, the future window was still risky (future risk=1.3910, gas d_ij=1.2840). The baseline would have executed into that window, while the agent avoided it.

### Example 3

- Start block: `24993874`
- Future block: `24993891`
- Agent state: `HIGH_STRESS`
- Agent action: `PAUSE`
- Start gas d_ij: `1.2624`
- Future gas d_ij: `1.2840`
- Future execution risk: `1.3910`
- Avoided bad exposure: `1.000000`
- Avoided future risk exposure: `1.390951`

**Plain-English read:** At block 24993874, the agent classified the network as HIGH_STRESS and chose PAUSE. 10 blocks later, the future window was still risky (future risk=1.3910, gas d_ij=1.2840). The baseline would have executed into that window, while the agent avoided it.

### Example 4

- Start block: `24993875`
- Future block: `24993891`
- Agent state: `HIGH_STRESS`
- Agent action: `PAUSE`
- Start gas d_ij: `1.2643`
- Future gas d_ij: `1.2840`
- Future execution risk: `1.3910`
- Avoided bad exposure: `1.000000`
- Avoided future risk exposure: `1.390951`

**Plain-English read:** At block 24993875, the agent classified the network as HIGH_STRESS and chose PAUSE. 10 blocks later, the future window was still risky (future risk=1.3910, gas d_ij=1.2840). The baseline would have executed into that window, while the agent avoided it.

### Example 5

- Start block: `24993876`
- Future block: `24993891`
- Agent state: `HIGH_STRESS`
- Agent action: `PAUSE`
- Start gas d_ij: `1.2582`
- Future gas d_ij: `1.2840`
- Future execution risk: `1.3910`
- Avoided bad exposure: `1.000000`
- Avoided future risk exposure: `1.390951`

**Plain-English read:** At block 24993876, the agent classified the network as HIGH_STRESS and chose PAUSE. 10 blocks later, the future window was still risky (future risk=1.3910, gas d_ij=1.2840). The baseline would have executed into that window, while the agent avoided it.

### Example 6

- Start block: `24993877`
- Future block: `24993891`
- Agent state: `HIGH_STRESS`
- Agent action: `PAUSE`
- Start gas d_ij: `1.2479`
- Future gas d_ij: `1.2840`
- Future execution risk: `1.3910`
- Avoided bad exposure: `1.000000`
- Avoided future risk exposure: `1.390951`

**Plain-English read:** At block 24993877, the agent classified the network as HIGH_STRESS and chose PAUSE. 10 blocks later, the future window was still risky (future risk=1.3910, gas d_ij=1.2840). The baseline would have executed into that window, while the agent avoided it.

### Example 7

- Start block: `24993878`
- Future block: `24993891`
- Agent state: `HIGH_STRESS`
- Agent action: `PAUSE`
- Start gas d_ij: `1.2428`
- Future gas d_ij: `1.2840`
- Future execution risk: `1.3910`
- Avoided bad exposure: `1.000000`
- Avoided future risk exposure: `1.390951`

**Plain-English read:** At block 24993878, the agent classified the network as HIGH_STRESS and chose PAUSE. 10 blocks later, the future window was still risky (future risk=1.3910, gas d_ij=1.2840). The baseline would have executed into that window, while the agent avoided it.

### Example 8

- Start block: `24993881`
- Future block: `24993891`
- Agent state: `HIGH_STRESS`
- Agent action: `PAUSE`
- Start gas d_ij: `1.2510`
- Future gas d_ij: `1.2840`
- Future execution risk: `1.3910`
- Avoided bad exposure: `1.000000`
- Avoided future risk exposure: `1.390951`

**Plain-English read:** At block 24993881, the agent classified the network as HIGH_STRESS and chose PAUSE. 10 blocks later, the future window was still risky (future risk=1.3910, gas d_ij=1.2840). The baseline would have executed into that window, while the agent avoided it.

### Example 9

- Start block: `24993891`
- Future block: `24993901`
- Agent state: `HIGH_STRESS`
- Agent action: `PAUSE`
- Start gas d_ij: `1.2840`
- Future gas d_ij: `1.0075`
- Future execution risk: `1.1757`
- Avoided bad exposure: `1.000000`
- Avoided future risk exposure: `1.175721`

**Plain-English read:** At block 24993891, the agent classified the network as HIGH_STRESS and chose PAUSE. 10 blocks later, the future window was still risky (future risk=1.1757, gas d_ij=1.0075). The baseline would have executed into that window, while the agent avoided it.

## Guardrail

These are counterfactual proxy examples, not live PnL. They show where the agent branch avoided a future bad execution window that the baseline branch would have entered. Real metrics like actual gas paid, slippage, fill price vs mid, and transaction success rate can be added later.