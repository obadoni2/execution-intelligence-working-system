# SPY Validation Plan

Goal:
Validate whether the frozen SUPT probe can produce useful execution-risk guidance on SPY market microstructure data.

Instrument:
SPY

Frozen probe:
- alpha = 0.01
- tail_n = 50
- no tuning
- no curve fitting

Required data:
- timestamp
- bid
- ask
- bid_size
- ask_size
- quote_updates
- trade_updates
- last_price
- volume

Validation gates:
1. Minimum 1,000+ windows
2. Walk-forward only
3. Compare against execute-always baseline
4. Measure future bad windows
5. Measure avoided risk exposure
6. Measure pause precision
7. Measure unnecessary pause rate
8. Measure discrimination gap

Success criteria:
- bad-exposure reduction >= 50%
- strong discrimination vs baseline
- pause decisions mostly align with future-bad windows
- no per-instrument retuning
