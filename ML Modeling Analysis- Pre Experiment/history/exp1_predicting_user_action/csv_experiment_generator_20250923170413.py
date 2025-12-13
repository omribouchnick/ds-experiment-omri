# # Generate the CSV exactly as requested:
# # - 3 priors: 0.2, 0.35, 0.5
# # - d' grid: 0.5..2.5 step 0.2 (inclusive → 11 values) for human and system
# # - 100 trials per row
# # - Column order:
# #   id, used, ps, dprime_h, dprime_s,
# #   event_t01..event_t100,
# #   h_t01..h_t100,
# #   s_t01..s_t100,
# #   ds_dec_t01..ds_dec_t100
# #
# # We'll also write the generator code to a .py file for reuse.

# import numpy as np
# import pandas as pd
# from pathlib import Path

# def arange_grid(start: float, stop: float, step: float):
#     vals = []
#     x = start
#     eps = 1e-9
#     while x <= stop + eps:
#         vals.append(round(x, 2))
#         x += step
#     return vals

# def gaussian_pdf(x, mu, sigma=1.0):
#     return np.exp(-0.5*((x-mu)/sigma)**2) / (np.sqrt(2*np.pi)*sigma)

# def means_from_dprime(dprime):
#     mu_s = +dprime/2.0
#     mu_n = -dprime/2.0
#     return mu_s, mu_n

# def sample_evts_exact(n_trials, ps, rng):
#     n_sig = int(round(n_trials * ps))
#     y = np.array([1]*n_sig + [0]*(n_trials - n_sig), dtype=np.int8)
#     rng.shuffle(y)
#     return y

# def sample_evidence(evts, dprime, rng):
#     mu_s, mu_n = means_from_dprime(dprime)
#     x = np.where(evts==1,
#                  rng.normal(mu_s, 1.0, size=evts.size),
#                  rng.normal(mu_n, 1.0, size=evts.size))
#     return x

# def ds_posterior(x_ds, ps, dprime_ds):
#     mu_s, mu_n = means_from_dprime(dprime_ds)
#     f_s = gaussian_pdf(x_ds, mu_s, 1.0)
#     f_n = gaussian_pdf(x_ds, mu_n, 1.0)
#     num = ps * f_s
#     den = num + (1-ps) * f_n
#     with np.errstate(divide='ignore', invalid='ignore'):
#         p = np.where(den > 0, num/den, 0.5)
#     return p

# def generate_conditions_csv(out_path: Path,
#                             ps_list=(0.2, 0.35, 0.5),
#                             d_start=0.5, d_stop=2.5, d_step=0.2,
#                             n_trials=100, seed=2025):
#     rng = np.random.default_rng(seed)
#     d_vals = arange_grid(d_start, d_stop, d_step)  # 11 values inclusive
#     rows = []
#     uid = 1

#     for ps in ps_list:                 # loop 1: priors
#         for d_h in d_vals:             # loop 2: d' human
#             for d_s in d_vals:         # loop 3: d' system
#                 # 1) events first with exact base rate
#                 evts = sample_evts_exact(n_trials, ps, rng)  # 1=Signal, 0=Noise
#                 # 2) human evidence
#                 x_h = sample_evidence(evts, d_h, rng)
#                 # 3) system evidence (independent draw, same event labels)
#                 x_s = sample_evidence(evts, d_s, rng)
#                 # 4) DS posterior & binary decision (0.5 MAP)
#                 p_ds = ds_posterior(x_s, ps, d_s)
#                 y_ds = (p_ds >= 0.5).astype(int)

#                 # Assemble row in requested order
#                 row = {
#                     "id": uid,
#                     "used": 0,
#                     "ps": float(ps),
#                     "dprime_h": float(d_h),
#                     "dprime_s": float(d_s),
#                 }
#                 # events first
#                 for i, yi in enumerate(evts, 1):
#                     row[f"event_t{i:02d}"] = "signal" if yi==1 else "noise"
#                 # 100 human
#                 for i, x in enumerate(x_h, 1):
#                     row[f"h_t{i:02d}"] = float(x)
#                 # 100 system
#                 for i, xs in enumerate(x_s, 1):
#                     row[f"s_t{i:02d}"] = float(xs)
#                 # 100 DS decisions
#                 for i, dd in enumerate(y_ds, 1):
#                     row[f"ds_dec_t{i:02d}"] = int(dd)

#                 rows.append(row)
#                 uid += 1

#     df = pd.DataFrame(rows)
#     # Explicit ordering to be safe
#     meta = ["id","used","ps","dprime_h","dprime_s"]
#     events = [f"event_t{i:02d}" for i in range(1, n_trials+1)]
#     human  = [f"h_t{i:02d}"     for i in range(1, n_trials+1)]
#     system = [f"s_t{i:02d}"     for i in range(1, n_trials+1)]
#     ds_bin = [f"ds_dec_t{i:02d}"for i in range(1, n_trials+1)]
#     df = df[meta + events + human + system + ds_bin]

#     out_path = Path(out_path)
#     df.to_csv(out_path, index=False)
#     return out_path, df.shape

# # Generate and save
# out_file = Path("data/conditions_experiment_3ps_11x11_100.csv")
# out_path, shape = generate_conditions_csv(out_file)
# shape
# generate_conditions.py
import numpy as np
import pandas as pd
from pathlib import Path

def arange_grid(start: float, stop: float, step: float):
    vals = []
    x = start
    eps = 1e-9
    while x <= stop + eps:
        vals.append(round(x, 2))
        x += step
    return vals

def gaussian_pdf(x, mu, sigma=1.0):
    return np.exp(-0.5*((x-mu)/sigma)**2) / (np.sqrt(2*np.pi)*sigma)

def means_from_dprime(dprime):
    mu_s = +dprime/2.0
    mu_n = -dprime/2.0
    return mu_s, mu_n

def sample_evts_exact(n_trials, ps, rng):
    """Exact base-rate per user: round(ps*100) signals, rest noise; then shuffle."""
    n_sig = int(round(n_trials * ps))
    y = np.array([1]*n_sig + [0]*(n_trials - n_sig), dtype=np.int8)
    rng.shuffle(y)
    return y  # 1=Signal, 0=Noise

def sample_evidence(evts, dprime, rng):
    """Sample evidence conditional on event labels under equal-variance SDT."""
    mu_s, mu_n = means_from_dprime(dprime)
    x = np.where(evts==1,
                 rng.normal(mu_s, 1.0, size=evts.size),
                 rng.normal(mu_n, 1.0, size=evts.size))
    return x

def ds_posterior(x_ds, ps, dprime_ds):
    """Bayesian posterior P(S|x) using equal-variance Gaussians and prior Ps."""
    mu_s, mu_n = means_from_dprime(dprime_ds)
    f_s = gaussian_pdf(x_ds, mu_s, 1.0)
    f_n = gaussian_pdf(x_ds, mu_n, 1.0)
    num = ps * f_s
    den = num + (1-ps) * f_n
    with np.errstate(divide='ignore', invalid='ignore'):
        p = np.where(den > 0, num/den, 0.5)
    return p

def generate_conditions_csv(out_path: Path,
                            ps_list=(0.2, 0.35, 0.5),
                            d_start=0.5, d_stop=2.5, d_step=0.2,
                            n_trials=100, seed=2025):
    rng = np.random.default_rng(seed)
    d_vals = arange_grid(d_start, d_stop, d_step)  # 11 values inclusive
    rows = []
    uid = 1

    # Three loops: Ps → d'_human → d'_system
    for ps in ps_list:
        for d_h in d_vals:
            for d_s in d_vals:
                # 1) Event sequence first
                evts = sample_evts_exact(n_trials, ps, rng)  # 1=Signal, 0=Noise
                # 2) Human evidence
                x_h = sample_evidence(evts, d_h, rng)
                # 3) DS evidence (independent draw, same labels)
                x_s = sample_evidence(evts, d_s, rng)
                # 4) DS posterior and binary decision (threshold 0.5)
                p_ds = ds_posterior(x_s, ps, d_s)
                y_ds = (p_ds >= 0.5).astype(int)

                # Assemble row in requested column order
                row = {
                    "id": uid,
                    "used": 0,
                    "ps": float(ps),
                    "dprime_h": float(d_h),
                    "dprime_s": float(d_s),
                }
                # events first
                for i, yi in enumerate(evts, 1):
                    row[f"event_t{i:02d}"] = "signal" if yi==1 else "noise"
                # 100 human
                for i, x in enumerate(x_h, 1):
                    row[f"h_t{i:02d}"] = float(x)
                # 100 system
                for i, xs in enumerate(x_s, 1):
                    row[f"s_t{i:02d}"] = float(xs)
                # 100 DS binary decisions
                for i, dd in enumerate(y_ds, 1):
                    row[f"ds_dec_t{i:02d}"] = int(dd)

                rows.append(row)
                uid += 1

    df = pd.DataFrame(rows)
    # Force final column order
    meta   = ["id","used","ps","dprime_h","dprime_s"]
    events = [f"event_t{i:02d}" for i in range(1, n_trials+1)]
    human  = [f"h_t{i:02d}"     for i in range(1, n_trials+1)]
    system = [f"s_t{i:02d}"     for i in range(1, n_trials+1)]
    ds_bin = [f"ds_dec_t{i:02d}"for i in range(1, n_trials+1)]
    df = df[meta + events + human + system + ds_bin]

    out_path = Path(out_path)
    df.to_csv(out_path, index=False)
    return out_path, df.shape

if __name__ == "__main__":
    out_file = Path("conditions_experiment_3ps_11x11_100.csv")
    out_path, shape = generate_conditions_csv(out_file)
    print("Wrote", out_path, "shape=", shape)
