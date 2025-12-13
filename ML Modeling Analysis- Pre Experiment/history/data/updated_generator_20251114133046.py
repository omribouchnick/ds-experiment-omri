# generate_sdt_conditions_v120.py
# SDT data generator for 3 priors × 11 d'H × 11 d'S, with 120 trials/row.
# Human & DS evidence: equal-variance Gaussians with means ±d'/2, sigma=1.
# DS decision (Version A): Bayesian posterior >= 0.5.
# Optional: force per-class moments and add custom-utility DS decisions.
#
# Output shape: (363, 5 + 4*n_trials) = (363, 485) when n_trials=120.

from pathlib import Path
import numpy as np
import pandas as pd
from math import sqrt, pi

# ---------------- CONFIG ----------------
N_TRIALS = 120                 # 10 + 10 + 100
SEED     = 2025
PS_LIST  = (0.2, 0.35, 0.5)
D_START, D_STOP, D_STEP = 0.5, 2.5, 0.2   # 11 values

# Moment matching controls
MATCH_MEANS = True             # force empirical mean(H|S/N) and mean(S|S/N) to ±d'/2
MATCH_SIGMA = False            # set to True to also force SD=1 per class

# Optional extra DS (utility) columns; set to None to skip
# Example scores: hit/cr=+1, miss=-2, fa=-1  -> tag "score_m2f1"
CUSTOM_DS = None
# CUSTOM_DS = {
#     "tag": "score_m2f1",
#     "scores": {"S_Hit": 1, "S_CR": 1, "S_Miss": -2, "S_FA": -1}
# }

OUT_CSV = Path("conditions_experiment_3ps_11x11_120_A.csv")  # base file
QC_CSV  = Path("QC_row_stats.csv")                            # per-row QC

# ---------------- UTILITIES ----------------
def arange_grid(start: float, stop: float, step: float):
    vals, x, eps = [], start, 1e-9
    while x <= stop + eps:
        vals.append(round(x, 2))
        x += step
    return vals

def gaussian_pdf(x, mu, sigma=1.0):
    return np.exp(-0.5*((x-mu)/sigma)**2) / (np.sqrt(2*pi)*sigma)

def means_from_dprime(dprime):
    mu_s = +dprime/2.0
    mu_n = -dprime/2.0
    return mu_s, mu_n

def sample_evts_exact(n_trials, ps, rng):
    """Exactly round(ps*n_trials) signals (1) and the rest noise (0), then shuffle."""
    n_sig = int(round(n_trials * float(ps)))
    y = np.array([1]*n_sig + [0]*(n_trials - n_sig), dtype=np.int8)
    rng.shuffle(y)
    return y  # 1=Signal, 0=Noise

def sample_evidence(evts, dprime, rng):
    mu_s, mu_n = means_from_dprime(dprime)
    return np.where(
        evts == 1,
        rng.normal(mu_s, 1.0, size=evts.size),
        rng.normal(mu_n, 1.0, size=evts.size)
    )

def force_moments(x, evts, dprime, match_means=True, match_sigma=False, target_sigma=1.0):
    """Per class (S/N) optionally enforce mean=±d'/2 and sd=target_sigma via linear transform."""
    mu_s, mu_n = means_from_dprime(dprime)
    out = x.copy()

    for label, target_mu in ((1, mu_s), (0, mu_n)):
        m = (evts == label)
        if not np.any(m): 
            continue
        xs = out[m]
        if match_sigma:
            sd = float(xs.std(ddof=0)) or 1.0
            xs = (xs - xs.mean()) / sd * target_sigma + target_mu
        elif match_means:
            xs = xs + (target_mu - xs.mean())
        out[m] = xs
    return out

def ds_posterior(x_ds, ps, dprime_ds):
    """Bayesian posterior P(S|x) under equal-variance SDT with prior ps."""
    mu_s, mu_n = means_from_dprime(dprime_ds)
    f_s = gaussian_pdf(x_ds, mu_s, 1.0)
    f_n = gaussian_pdf(x_ds, mu_n, 1.0)
    num = float(ps) * f_s
    den = num + (1.0 - float(ps)) * f_n
    with np.errstate(divide='ignore', invalid='ignore'):
        p = np.where(den > 0, num/den, 0.5)
    return p

def ds_decision_custom_score(x_ds, ps, dprime_ds, scores: dict):
    """
    DS decision by expected-score optimality:
      decide 'Signal' if LR > Criterion,
      LR = f_S/f_N,  Criterion = (P(N)/P(S)) * ((S_CR - S_FA)/(S_Hit - S_Miss))
    """
    mu_s, mu_n = means_from_dprime(dprime_ds)
    f_s = gaussian_pdf(x_ds, mu_s, 1.0)
    f_n = gaussian_pdf(x_ds, mu_n, 1.0)
    with np.errstate(divide='ignore', invalid='ignore'):
        LR = f_s / f_n

    K = (scores['S_CR'] - scores['S_FA']) / (scores['S_Hit'] - scores['S_Miss'])
    criterion = ((1.0 - float(ps)) / float(ps)) * K
    return (LR > criterion).astype(int)

# ---------------- MAIN GENERATOR ----------------
def generate_conditions_csv(
    out_path: Path,
    ps_list=PS_LIST,
    d_start=D_START, d_stop=D_STOP, d_step=D_STEP,
    n_trials=N_TRIALS, seed=SEED,
    match_means=MATCH_MEANS, match_sigma=MATCH_SIGMA,
    custom_ds=CUSTOM_DS
):
    rng = np.random.default_rng(seed)
    d_vals = arange_grid(d_start, d_stop, d_step)  # 11 values
    rows = []
    uid = 1

    for ps in ps_list:
        for d_h in d_vals:
            for d_s in d_vals:
                # 1) labels with exact base-rate
                evts = sample_evts_exact(n_trials, ps, rng)

                # 2) Human & DS evidence
                x_h = sample_evidence(evts, d_h, rng)
                x_s = sample_evidence(evts, d_s, rng)

                # Optional per-class moment matching
                if match_means or match_sigma:
                    x_h = force_moments(x_h, evts, d_h, match_means, match_sigma)
                    x_s = force_moments(x_s, evts, d_s, match_means, match_sigma)

                # 3) DS posterior and Version-A decisions
                p_ds = ds_posterior(x_s, ps, d_s)
                y_ds = (p_ds >= 0.5).astype(int)

                # 4) Optional custom-utility DS decisions
                if custom_ds is not None:
                    y_ds_custom = ds_decision_custom_score(x_s, ps, d_s, custom_ds["scores"])

                # Row assembly (keeps your column order)
                row = {"id": uid, "used": 0, "ps": float(ps), "dprime_h": float(d_h), "dprime_s": float(d_s)}
                for i, yi in enumerate(evts, 1): row[f"event_t{i:02d}"] = "signal" if yi == 1 else "noise"
                for i, x in enumerate(x_h, 1):  row[f"h_t{i:02d}"]     = float(x)
                for i, x in enumerate(x_s, 1):  row[f"s_t{i:02d}"]     = float(x)
                for i, dd in enumerate(y_ds, 1): row[f"ds_dec_t{i:02d}"] = int(dd)
                if custom_ds is not None:
                    for i, dd in enumerate(y_ds_custom, 1):
                        row[f"ds_{custom_ds['tag']}_t{i:02d}"] = int(dd)

                rows.append(row); uid += 1

    # DataFrame + exact column order
    df = pd.DataFrame(rows)
    meta   = ["id","used","ps","dprime_h","dprime_s"]
    events = [f"event_t{i:02d}" for i in range(1, n_trials+1)]
    human  = [f"h_t{i:02d}"     for i in range(1, n_trials+1)]
    system = [f"s_t{i:02d}"     for i in range(1, n_trials+1)]
    ds_bin = [f"ds_dec_t{i:02d}"for i in range(1, n_trials+1)]
    cols   = meta + events + human + system + ds_bin

    # If custom DS requested, append those columns to the order
    if CUSTOM_DS is not None:
        cols += [f"ds_{CUSTOM_DS['tag']}_t{i:02d}" for i in range(1, n_trials+1)]

    df = df[cols]

    out_path = Path(out_path)
    df.to_csv(out_path, index=False)
    return df

# ---------------- QC / VALIDATION ----------------
def quick_qc(df: pd.DataFrame, n_trials=N_TRIALS, out_csv=QC_CSV):
    """Per-row checks: counts, per-class means and SDs, and abs errors vs targets."""
    def grab(row, prefix):
        return row[[f"{prefix}_t{i:02d}" for i in range(1, n_trials+1)]].values.astype(float)

    def labels(row):
        lab = row[[f"event_t{i:02d}" for i in range(1, n_trials+1)]].values
        return (lab == "signal").astype(int)

    recs = []
    for _, r in df.iterrows():
        ps, dH, dS = float(r.ps), float(r.dprime_h), float(r.dprime_s)
        ev = labels(r)
        xh = grab(r, "h")
        xs = grab(r, "s")

        mS = ev == 1; mN = ~mS

        # counts
        nS, nN = int(mS.sum()), int(mN.sum())
        # targets
        muHs, muHn = dH/2.0, -dH/2.0
        muSs, muSn = dS/2.0, -dS/2.0

        # empirical
        hS_mu, hN_mu = (xh[mS].mean() if nS else np.nan), (xh[mN].mean() if nN else np.nan)
        sS_mu, sN_mu = (xs[mS].mean() if nS else np.nan), (xs[mN].mean() if nN else np.nan)
        hS_sd, hN_sd = (xh[mS].std(ddof=0) if nS else np.nan), (xh[mN].std(ddof=0) if nN else np.nan)
        sS_sd, sN_sd = (xs[mS].std(ddof=0) if nS else np.nan), (xs[mN].std(ddof=0) if nN else np.nan)

        recs.append({
            "id": int(r.id), "ps": ps, "dprime_h": dH, "dprime_s": dS,
            "n_signal": nS, "n_noise": nN,
            "mean_H|S": hS_mu, "mean_H|N": hN_mu, "mean_S|S": sS_mu, "mean_S|N": sN_mu,
            "sd_H|S": hS_sd, "sd_H|N": hN_sd, "sd_S|S": sS_sd, "sd_S|N": sN_sd,
            "abs_err_H|S": abs(hS_mu - muHs) if nS else np.nan,
            "abs_err_H|N": abs(hN_mu - muHn) if nN else np.nan,
            "abs_err_S|S": abs(sS_mu - muSs) if nS else np.nan,
            "abs_err_S|N": abs(sN_mu - muSn) if nN else np.nan,
        })

    qc = pd.DataFrame(recs)
    qc.to_csv(out_csv, index=False)

    # Print a short summary
    def summ(col): 
        s = qc[col].dropna()
        return f"median={s.median():.3f}, mean={s.mean():.3f}, max={s.max():.3f}"

    print("\nQC — counts:")
    print("  n_signal  ~ round(ps * n_trials)  (check in QC_row_stats.csv)")

    print("\nQC — absolute mean errors vs targets (should be small; 0 if forced):")
    for c in ["abs_err_H|S","abs_err_H|N","abs_err_S|S","abs_err_S|N"]:
        print(f"  {c}: {summ(c)}")

    return qc

# ---------------- RUN ----------------
if __name__ == "__main__":
    df = generate_conditions_csv(OUT_CSV)
    print(f"Wrote {OUT_CSV}  shape={df.shape}")  # Expect (363, 485) without custom DS; +120 if custom DS on
    quick_qc(df, n_trials=N_TRIALS)
