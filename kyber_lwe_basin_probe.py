import numpy as np
import math
import random

Q = 3329
N = 64
RESTARTS = 5
STEPS = 200


def phi(x):
    x = np.asarray(x, dtype=np.float64)
    energy = np.mean(x * x) + 1e-9
    return math.log2(energy)


def make_kyber_like_matrix(n=N, q=Q, seed=42):
    rng = np.random.default_rng(seed)
    A = rng.integers(0, q, size=(n, n))
    top = np.concatenate([q * np.eye(n), np.zeros((n, n))], axis=1)
    bottom = np.concatenate([A, np.eye(n)], axis=1)
    return np.concatenate([top, bottom], axis=0)


def random_lattice_vector(dim):
    return np.random.randint(-Q // 2, Q // 2, size=dim)


def local_descent(B, x):
    best = x.copy()
    best_phi = phi(B @ best)

    for _ in range(STEPS):
        improved = False

        for _ in range(200):
            cand = best.copy()
            idx = random.randrange(len(cand))
            cand[idx] += random.choice([-1, 1])

            cand_phi = phi(B @ cand)

            if cand_phi < best_phi:
                best = cand
                best_phi = cand_phi
                improved = True
                break

        if not improved:
            break

    return best_phi


def run():
    B = make_kyber_like_matrix()
    dim = B.shape[1]

    print("=" * 72)
    print("KYBER CANONICAL LWE BASIN / DESCENT PROBE")
    print("=" * 72)
    print(f"q={Q}, n={N}, lattice_dim={B.shape}")
    print()

    random_phis = []
    end_phis = []

    for r in range(RESTARTS):
        x0 = random_lattice_vector(dim)
        start_phi = phi(B @ x0)
        end_phi = local_descent(B, x0)

        random_phis.append(start_phi)
        end_phis.append(end_phi)

        print(
            f"Restart {r}: start phi={start_phi:.4f} "
            f"-> end phi={end_phi:.4f}"
        )

    print()
    print("SUMMARY")
    print(f"random plateau phi: {np.mean(random_phis):.4f} +/- {np.std(random_phis):.4f}")
    print(f"descent end phi:    {np.mean(end_phis):.4f} +/- {np.std(end_phis):.4f}")

    if min(end_phis) < np.mean(random_phis) - 1.0:
        print("Result: descent found lower-phi movement.")
    else:
        print("Result: descent stalled near random plateau.")

    print()
    print(
        "Interpretation: this tests structural reachability only. "
        "It does not perform secret recovery."
    )


if __name__ == "__main__":
    run()
