#!/usr/bin/env python3
"""
CAOL Experiment 2 — Negative regime: slow KL decay
===================================================
Shows the boundary where certification becomes expensive/loose:
- Slow eigenvalue decay (k^{-0.5} vs k^{-2}) → operator manifold has slow
  Kolmogorov width decay → greedy enrichment stalls
- Large perturbation (σ=1.0) → small coercivity α → loose certificate
- Large residual variance → B large → MC needs more samples

Compare against baseline (k^{-2}, σ=0.3).
"""

import sys, time, os
import numpy as np
from numpy.polynomial.legendre import legval
from scipy.sparse.linalg import spsolve, factorized
from scipy import sparse as sp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from skfem import MeshLine, ElementLineP1, InteriorBasis, BilinearForm, LinearForm
from skfem import condense
from skfem.helpers import dot, grad

os.makedirs("figures", exist_ok=True)
np.random.seed(42)

# ═══════════════════════════════════════════════════════════════════════════
#  Parameters — SLOW regime
# ═══════════════════════════════════════════════════════════════════════════

n_mesh  = 101
n_fine  = 201
M_KL    = 8
decay_power = 0.5          # λ_k = k^{-p}, p=0.5 for slow decay
sigma   = 1.0
a0      = 3.0              # mean field (larger to compensate high σ)
f_val   = 1.0

ks      = np.arange(1, M_KL + 1)
lambdas = 1.0 / ks ** decay_power
α_c = a0 - sigma * np.sqrt((lambdas).sum())
print(f"  α≈{α_c:.4f} (should be >0 for coercivity)")

print("=" * 62)
print("  CAOL Experiment 2 — Slow KL decay (negative regime)")
print("=" * 62)
print(f"  1D FE, mesh {n_mesh}, KL M={M_KL}, decay k^-{decay_power}")
print(f"  σ={sigma}, a₀={a0}, α≈{α_c:.4f}")

# ═══════════════════════════════════════════════════════════════════════════
#  FEM in 1D
# ═══════════════════════════════════════════════════════════════════════════

@BilinearForm
def diffusion(u, v, w):
    return w.a * dot(grad(u), grad(v))

@LinearForm
def load(v, w):
    return f_val * v

mesh = MeshLine(np.linspace(0, 1, n_mesh))
basis = InteriorBasis(mesh, ElementLineP1(), intorder=3)
D = basis.get_dofs(lambda x: (x[0]==0)|(x[0]==1))
N = basis.N

mesh_fine = MeshLine(np.linspace(0, 1, n_fine))
basis_fine = InteriorBasis(mesh_fine, ElementLineP1(), intorder=3)
D_fine = basis_fine.get_dofs(lambda x: (x[0]==0)|(x[0]==1))

b_fixed = load.assemble(basis)
K0_mat = diffusion.assemble(basis, a=np.ones(N)*a0)
_, _, _, interior = condense(K0_mat, b_fixed, D=D)
K0_int = K0_mat[interior][:, interior]
K0_fact = factorized(K0_int.tocsc())
b_int = b_fixed[interior]

kl_int = []
for k in ks:
    @BilinearForm
    def kl_fn(u, v, w, kk=k):
        return (np.sin(np.pi*kk*w.x[0]) * dot(grad(u), grad(v)))
    A = kl_fn.assemble(basis)
    kl_int.append(A[interior][:, interior].tocsc())

def assemble_A(y):
    A = K0_int.copy().tocsc()
    for i in range(M_KL):
        A += y[i]*np.sqrt(lambdas[i])*kl_int[i]
    return A

def solve_pde(y):
    A = assemble_A(y)
    u_int = spsolve(A.tocsr(), b_int)
    u = np.zeros(N); u[interior] = u_int; return u

def v_norm_sq(u):
    return float(u @ (K0_mat @ u))

def residual_Vprime_norm(y, u_ap):
    A_int = assemble_A(y)
    R_int = b_int - A_int @ u_ap[interior]
    r_int = K0_fact(R_int)
    return np.sqrt(float(R_int @ r_int))

# ═══════════════════════════════════════════════════════════════════════════
#  Polynomial operator + weak-greedy
# ═══════════════════════════════════════════════════════════════════════════

class PolyOp:
    def __init__(self, M):
        self.M = M
        self.coeffs = []
        self.n = 0
    def eval(self, y):
        u = np.zeros(N)
        for alpha, c in self.coeffs:
            psi = 1.0
            for d in range(self.M):
                ei = [0]*(alpha[d]+1); ei[alpha[d]]=1
                psi *= legval(y[d], ei)
            u += psi*c
        return u
    def add(self, alpha, c):
        self.coeffs.append((alpha, c)); self.n += 1

def all_indices(M, max_deg):
    idx = []
    for total in range(max_deg+1):
        def gen(d, rem, cur):
            if d==1: idx.append(tuple(cur+[rem]))
            else:
                for v in range(rem+1): gen(d-1, rem-v, cur+[v])
        gen(M, total, [])
    return idx

def greedy_enrich(op, train_y, train_u, candidates):
    n_tr = len(train_y)
    best_α = None; best_c = None; best_red = -np.inf
    for α in candidates:
        if any(α == a for a,_ in op.coeffs): continue
        psi = np.ones(n_tr)
        for d in range(op.M):
            for i in range(n_tr):
                ei = [0]*(α[d]+1); ei[α[d]]=1
                psi[i] *= legval(train_y[i][d], ei)
        num = np.zeros(N); den = 0.0
        for i in range(n_tr):
            e_i = train_u[i] - op.eval(train_y[i])
            num += psi[i]*e_i; den += psi[i]**2
        if den < 1e-14: continue
        c = num/den
        red = 0.0
        for i in range(n_tr):
            e_old = train_u[i] - op.eval(train_y[i])
            e_new = e_old - psi[i]*c
            red += v_norm_sq(e_old) - v_norm_sq(e_new)
        if red > best_red:
            best_red = red; best_α = α; best_c = c
    if best_α is not None and best_red > 1e-14:
        op.add(best_α, best_c); return True
    return False

# ═══════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════

print("\nGenerating samples...")
N_tr = 200; N_te = 100
train_y = [np.random.uniform(-1,1,M_KL) for _ in range(N_tr)]
train_u = [solve_pde(y) for y in train_y]
test_y  = [np.random.uniform(-1,1,M_KL) for _ in range(N_te)]
test_u  = [solve_pde(y) for y in test_y]
print(f"  {N_tr} train, {N_te} test")

candidates = all_indices(M_KL, 2)
candidates = [c for c in candidates if any(cd>0 for cd in c)]
print(f"  Candidates (deg 1-2): {len(candidates)}")

op = PolyOp(M_KL)
u_mean = np.mean(train_u, axis=0)
op.add(tuple([0]*M_KL), u_mean)

M_MC = 200; max_steps = 20
n_hist, err_hist, cert_hist, eff_hist = [], [], [], []
B_hist = []

print("\nAdaptive enrichment:")
for step in range(max_steps):
    err_sq = 0.0
    for i in range(N_te):
        err_sq += v_norm_sq(test_u[i] - op.eval(test_y[i]))
    err = np.sqrt(err_sq/N_te)

    cert_sq = 0.0; B_est = 0.0
    for _ in range(M_MC):
        y = np.random.uniform(-1,1,M_KL)
        rn = residual_Vprime_norm(y, op.eval(y))
        cert_sq += rn**2
        B_est = max(B_est, rn**2)
    cert = np.sqrt(cert_sq/M_MC)
    eff = cert/max(err,1e-15)

    n_hist.append(op.n); err_hist.append(err)
    cert_hist.append(cert); eff_hist.append(eff)
    B_hist.append(B_est)

    print(f"  Step {step:2d} n={op.n:2d} | err={err:.4e} | cert={cert:.4e} | "
          f"eff={eff:.2f} | B={B_est:.4e}")

    if err < 1e-5 or op.n >= 80: break
    ok = greedy_enrich(op, train_y[:100], train_u[:100], candidates)
    if not ok: print("  Stalled"); break

# MC convergence: reference eta and B
M_ref = 2000
cert_ref_sq = 0.0; B_ref = 0.0
for _ in range(M_ref):
    y = np.random.uniform(-1,1,M_KL)
    rn = residual_Vprime_norm(y, op.eval(y))
    cert_ref_sq += rn**2
    B_ref = max(B_ref, rn**2)
eta_ref = np.sqrt(cert_ref_sq/M_ref)

M_range = [10,25,50,100,200,500]
mc_errors = []
for M in M_range:
    e = []
    for _ in range(30):
        cs = 0.0
        for __ in range(M):
            y = np.random.uniform(-1,1,M_KL)
            cs += residual_Vprime_norm(y, op.eval(y))**2
        e.append(abs(np.sqrt(cs/M) - eta_ref))
    mc_errors.append(np.mean(e))

# ═══════════════════════════════════════════════════════════════════════════
#  Baseline comparison data
# ═══════════════════════════════════════════════════════════════════════════

baseline = {
    'err_final': 2.03e-3, 'cert_final': 2.00e-3,
    'eff_final': 0.98, 'eta_ref': 1.91e-3,
    'M500_err': 4.24e-5, 'B': None,  # B not measured in baseline
    'α': 0.8145, 'decay': 'k^-2', 'σ': 0.3
}

# ═══════════════════════════════════════════════════════════════════════════
#  Comparison table
# ═══════════════════════════════════════════════════════════════════════════

print("\n" + "="*62)
print("  Comparison: Baseline vs Slow-KL Regime")
print("="*62)
print(f"  {'':>25} {'Baseline (k^-2)':>18} {'Slow (k^-0.5)':>18}")
print(f"  {'Coercivity α':>25} {baseline['α']:>18.4f} {α_c:>18.4f}")
print(f"  {'Final error':>25} {baseline['err_final']:>18.4e} {err_hist[-1]:>18.4e}")
print(f"  {'Final certificate':>25} {baseline['cert_final']:>18.4e} {cert_hist[-1]:>18.4e}")
print(f"  {'Final effectivity':>25} {baseline['eff_final']:>18.2f} {eff_hist[-1]:>18.2f}")
B_label = 'B (max ||R||_Vprime^2)'
print("  " + B_label.rjust(25) + " " + "N/A".rjust(18) + " " + f"{B_ref:>18.4e}")
print(f"  {'η_ref':>25} {baseline['eta_ref']:>18.4e} {eta_ref:>18.4e}")
print(f"  {'MC err M=500':>25} {baseline['M500_err']:>18.4e} {mc_errors[-1] if len(mc_errors)>0 else 'N/A':>18}")
print(f"  {'Error reduction':>25} {'7.5×':>18} {err_hist[0]/max(err_hist[-1],1e-15):>18.1f}×")
print(f"  {'Steps until stall':>25} {'~N/A (continues)':>18} {len(n_hist):>18}")

# ═══════════════════════════════════════════════════════════════════════════
#  Figures
# ═══════════════════════════════════════════════════════════════════════════

n_arr = np.array(n_hist); err_arr = np.array(err_hist)
cert_arr = np.array(cert_hist); eff_arr = np.array(eff_hist)

# Plot 1: Error convergence (slow vs baseline)
fig, ax = plt.subplots(figsize=(6,4))
ax.semilogy(n_arr, err_arr, 'o-', color='#d62728', label='Slow KL (k^-0.5) error')
ax.semilogy(n_arr, cert_arr, 's--', color='#ff7f0e', label='Slow KL cert')
ax.axhline(y=baseline['err_final'], color='#1f77b4', ls=':', label='Baseline final error')
ax.set_xlabel('n'); ax.set_ylabel('Error / Certificate')
ax.set_title('Negative regime: slow KL decay')
ax.legend(); ax.grid(True, alpha=0.3)
fig.tight_layout(); fig.savefig('figures/fig5_slow_kl_convergence.pdf')
print("  -> figures/fig5_slow_kl_convergence.pdf")

# Plot 2: B estimate vs n (showing growth)
fig, ax = plt.subplots(figsize=(6,4))
ax.semilogy(n_arr, B_hist[:len(n_arr)], 'o-', color='#9467bd')
ax.set_xlabel('n'); ax.set_ylabel('B = max ‖R‖_{V\'}^2')
ax.set_title('Residual bound B grows with enrichment (slow KL)')
ax.grid(True, alpha=0.3)
fig.tight_layout(); fig.savefig('figures/fig6_B_growth.pdf')
print("  -> figures/fig6_B_growth.pdf")

# ═══════════════════════════════════════════════════════════════════════════
#  Save data
# ═══════════════════════════════════════════════════════════════════════════

np.savez('figures/experiment_slow_data.npz',
         n_arr=n_arr, err_arr=err_arr, cert_arr=cert_arr,
         eff_arr=eff_arr, B_hist=np.array(B_hist[:len(n_arr)]),
         M_arr=np.array(M_range), mc_errors=mc_errors,
         eta_ref=eta_ref, B_ref=B_ref, α_c=α_c)
print("  Saved figures/experiment_slow_data.npz")
print("Done.")
