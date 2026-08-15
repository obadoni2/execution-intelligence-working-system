def classify_regime(dij: float) -> str:
    if dij < 1.0:
        return "COHERENCE"
    if dij < 2.0:
        return "CLUTCH"
    if dij < 3.6:
        return "SUB-FLOOR"
    return "VACUUM"


def regime_description(dij: float) -> str:
    regime = classify_regime(dij)

    if regime == "COHERENCE":
        return "Ordered / stable structural regime."
    if regime == "CLUTCH":
        return "Adaptive stress / congestion regime."
    if regime == "SUB-FLOOR":
        return "Disordered regime with elevated structural stress."
    return "Extreme disorder / vacuum band."