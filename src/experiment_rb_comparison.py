#!/usr/bin/env python3
"""
CAOL Experiment 3 — CAOL vs Reduced Basis comparison
======================================================
Compare CAOL (polynomial chaos operator learning) against
standard Reduced Basis (RB) on the same 2D affine diffusion problem.

RB builds a linear subspace V_n = span{ξ_1,...,ξ_n} where ξ_i are
PDE snapshots at greedily selected parameters. Certification via
deterministic residual bound.

CAOL uses the polynomial chaos operator with weak-greedy enrichment.

Metrics: convergence rate, certificate effectivity, computational cost.
"""

import sys, time, os
import numpy as np
from numpy.polynomial.legendre import legval
from scipy.sparse.linalg import spsolve, factorized
from scipy import sparse as sp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from skfem import MeshQuad, ElementQuad1, InteriorBasis, BilinearForm, LinearForm
from skfem import condense
from skfem.helpers import dot, grad

os.makedirs("figures", exist_ok=True)
np.random.seed(42)

# ═══════════════════════════════════════════════════════════════════════════
#  Problem (same as Experiment 1)
# ═══════════════════════════════════════════════════════════════════════════

n_mesh  = 25
M_KL    = 8
sigma   = 0.3
a0      = 2.0
f_val   = 1.0
ks      = np.arange(1, M_KL+1)
lambdas = 1.0 / ks**2
a_coer  = a0 - sigma * np.sqrt((lambdas).sum())
print("="*62)
print("  CAOL vs RB Comparison")
print("="*62)
print(f"  2D affine diffusion, 25x25 mesh, M={M_KL} KL, σ={sigma}, a₀={a0}")

# ── FEM ─────────────────────────────────────────────────────────────────

@BilinearForm
def diffusion(u, v, w): return w.a * dot(grad(u), grad(v))
@LinearForm
def load(v, w): return f_val * v

mesh = MeshQuad.init_tensor(np.linspace(0,1,n_mesh), np.linspace(0,1,n_mesh))
basis = InteriorBasis(mesh, ElementQuad1(), intorder=3)
D = basis.get_dofs(lambda x: (x[0]==0)|(x[0]==1)|(x[1]==0)|(x[1]==1))
N = basis.N
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
        return (np.sin(np.pi*kk*w.x[0])*np.sin(np.pi*kk*w.x[1])*dot(grad(u),grad(v)))
    A = kl_fn.assemble(basis)
    kl_int.append(A[interior][:, interior].tocsc())

def assemble_A(y):
    A = K0_int.copy().tocsc()
    for i in range(M_KL): A += y[i]*np.sqrt(lambdas[i])*kl_int[i]
    return A

def solve_pde(y):
    A = assemble_A(y)
    u_int = spsolve(A.tocsr(), b_int)
    u = np.zeros(N); u[interior] = u_int; return u

def v_norm_sq(u): return float(u @ (K0_mat @ u))
def v_norm(u): return np.sqrt(v_norm_sq(u))

def residual_Vprime_norm(y, u_ap):
    A_int = assemble_A(y)
    R_int = b_int - A_int @ u_ap[interior]
    r_int = K0_fact(R_int)
    return np.sqrt(float(R_int @ r_int))

# Estimate β (continuity constant) — max eigenvalue of A(y) in A₀ norm
print("Estimating β...")
beta_est = 0.0
for _ in range(100):
    y = np.random.uniform(-1, 1, M_KL)
    A_int = assemble_A(y)
    # Rayleigh quotient: v^T A v / v^T K0 v, maximised
    # Use power iteration for max eigenvalue of K0^{-1} A
    v = np.random.randn(len(b_int))
    v = v / np.linalg.norm(v)
    for _ in range(20):
        w = K0_fact(A_int @ v)
        lam = np.dot(v, w)
        v = w / np.linalg.norm(w)
    beta_est = max(beta_est, lam)
print(f"  α (coercivity) ≈ {a_coer/a0:.4f}, β (continuity) ≈ {beta_est:.4f}")
print(f"  Certificate effectivity bound: [α/β, β/α] ≈ [{a_coer/a0/beta_est:.3f}, {beta_est*a0/a_coer:.3f}]")

# ═══════════════════════════════════════════════════════════════════════════
#  Samples
# ═══════════════════════════════════════════════════════════════════════════

N_tr = 200; N_te = 100
train_y = [np.random.uniform(-1,1,M_KL) for _ in range(N_tr)]
train_u = [solve_pde(y) for y in train_y]
test_y  = [np.random.uniform(-1,1,M_KL) for _ in range(N_te)]
test_u  = [solve_pde(y) for y in test_y]
M_MC = 200
print(f"  {N_tr} train, {N_te} test, M_MC={M_MC}")

# ═══════════════════════════════════════════════════════════════════════════
#  Method 1: Reduced Basis (standard greedy)
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- Reduced Basis ---")
t_rb = time.perf_counter()

# Greedy training set for snapshot selection
rb_greedy_set = [np.random.uniform(-1,1,M_KL) for _ in range(400)]
rb_snapshots = []     # list of (y, u_vec, residual_norm)
rb_basis = []         # orthonormalised snapshot vectors (interior only)
rb_Ut = None          # basis matrix (n_basis x n_int)

def rb_project(y):
    """Galerkin projection: solve A_n(y) c_n = f_n where A_n = U^T A(y) U"""
    A_int = assemble_A(y)
    U = rb_Ut  # (n_int x n_basis), dense
    # Galerkin system
    A_n = U.T @ (A_int @ U)  # (n_basis x n_basis), dense
    f_n = U.T @ b_int        # (n_basis,)
    c_n = np.linalg.solve(A_n, f_n)
    u_n_int = U @ c_n
    u_n = np.zeros(N); u_n[interior] = u_n_int
    return u_n

# Greedy loop
rb_n_hist, rb_err_hist, rb_cert_hist = [], [], []
rb_cost_hist = []  # cumulative PDE solves

for rb_step in range(25):
    if rb_step == 0:
        # First snapshot: solve at y=0 (mean)
        y0 = np.zeros(M_KL)
        u0 = solve_pde(y0)
        u0_int = u0[interior]
        # Orthonormalise
        nrm = np.sqrt(u0_int @ (K0_int @ u0_int))
        rb_basis.append(u0_int / nrm)
        rb_Ut = np.column_stack(rb_basis)
        rb_err = np.inf
    else:
        # Greedy selection: find y with largest residual norm
        best_err = -np.inf
        best_y = None
        for y_g in rb_greedy_set:
            u_ap = rb_project(y_g)
            rn = residual_Vprime_norm(y_g, u_ap)
            if rn > best_err: best_err = rn; best_y = y_g
        # Solve at the selected parameter and add to basis
        u_new = solve_pde(best_y)
        u_new_int = u_new[interior]
        # Orthonormalise against existing basis
        u_new_int = u_new_int - rb_Ut @ (rb_Ut.T @ (K0_int @ u_new_int))
        nrm = np.sqrt(u_new_int @ (K0_int @ u_new_int))
        if nrm < 1e-12: break
        rb_basis.append(u_new_int / nrm)
        rb_Ut = np.column_stack(rb_basis)

    n = len(rb_basis)
    rb_Ut = np.column_stack(rb_basis)

    # Error on test set
    err_sq = 0.0
    for i in range(N_te):
        u_ap = rb_project(test_y[i])
        err_sq += v_norm_sq(test_u[i] - u_ap)
    err = np.sqrt(err_sq / N_te)

    # MC certificate
    cert_sq = 0.0
    for _ in range(M_MC):
        y = np.random.uniform(-1,1,M_KL)
        u_ap = rb_project(y)
        cert_sq += residual_Vprime_norm(y, u_ap)**2
    cert = np.sqrt(cert_sq / M_MC)

    rb_n_hist.append(n); rb_err_hist.append(err); rb_cert_hist.append(cert)
    # Cost: n PDE solves (one per greedy step) + test set evaluations
    rb_cost_hist.append(n + N_te * n * n / 10000)  # rough cost model

    print(f"  RB n={n:2d} | err={err:.4e} | cert={cert:.4e} "
          f"| eff={cert/max(err,1e-15):.2f}")

t_rb_end = time.perf_counter()
print(f"  RB time: {t_rb_end-t_rb:.1f}s")

# ═══════════════════════════════════════════════════════════════════════════
#  Method 2: CAOL (Polynomial Chaos, from Experiment 1)
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- CAOL (Polynomial Chaos) ---")
t_ca = time.perf_counter()

class PolyOp:
    def __init__(self, M):
        self.M = M; self.coeffs = []; self.n = 0
    def eval(self, y):
        u = np.zeros(N)
        for a,c in self.coeffs:
            psi = 1.0
            for d in range(self.M):
                ei = [0]*(a[d]+1); ei[a[d]]=1
                psi *= legval(y[d], ei)
            u += psi*c
        return u
    def add(self, a, c): self.coeffs.append((a,c)); self.n += 1

def all_indices(M, md):
    idx = []
    for t in range(md+1):
        def gen(d, r, cur):
            if d==1: idx.append(tuple(cur+[r]))
            else:
                for v in range(r+1): gen(d-1, r-v, cur+[v])
        gen(M, t, [])
    return idx

candidates = [c for c in all_indices(M_KL, 3) if any(cd>0 for cd in c)]

op = PolyOp(M_KL)
u_mean = np.mean(train_u, axis=0)
op.add(tuple([0]*M_KL), u_mean)

ca_n_hist, ca_err_hist, ca_cert_hist = [], [], []

for step in range(20):
    err_sq = 0.0
    for i in range(N_te): err_sq += v_norm_sq(test_u[i] - op.eval(test_y[i]))
    err = np.sqrt(err_sq/N_te)

    cert_sq = 0.0
    for _ in range(M_MC):
        y = np.random.uniform(-1,1,M_KL)
        cert_sq += residual_Vprime_norm(y, op.eval(y))**2
    cert = np.sqrt(cert_sq/M_MC)

    ca_n_hist.append(op.n); ca_err_hist.append(err); ca_cert_hist.append(cert)
    print(f"  CAOL n={op.n:2d} | err={err:.4e} | cert={cert:.4e} "
          f"| eff={cert/max(err,1e-15):.2f}")

    if op.n >= 60: break
    # Greedy enrichment
    best_a = None; best_c = None; best_red = -np.inf
    for a in candidates:
        if any(a == aa for aa,_ in op.coeffs): continue
        psi = np.ones(N_tr)
        for d in range(op.M):
            for i in range(N_tr):
                ei = [0]*(a[d]+1); ei[a[d]]=1
                psi[i] *= legval(train_y[i][d], ei)
        num = np.zeros(N); den = 0.0
        for i in range(N_tr):
            e_i = train_u[i] - op.eval(train_y[i])
            num += psi[i]*e_i; den += psi[i]**2
        if den < 1e-14: continue
        c = num/den
        red = 0.0
        for i in range(N_tr):
            eo = train_u[i] - op.eval(train_y[i])
            en = eo - psi[i]*c
            red += v_norm_sq(eo) - v_norm_sq(en)
        if red > best_red: best_red=red; best_a=a; best_c=c
    if best_a is not None and best_red > 1e-14:
        op.add(best_a, best_c)
    else: break

t_ca_end = time.perf_counter()
print(f"  CAOL time: {t_ca_end-t_ca:.1f}s")

# ═══════════════════════════════════════════════════════════════════════════
#  Summary table
# ═══════════════════════════════════════════════════════════════════════════

print("\n" + "="*62)
print("  Comparison: RB vs CAOL")
print("="*62)

# Match by n
min_n = min(len(rb_n_hist), len(ca_n_hist))
print(f"  {'':>20} {'RB':>18} {'CAOL':>18}")
print(f"  {'Final n':>20} {rb_n_hist[-1]:>18} {ca_n_hist[-1]:>18}")
print(f"  {'Final error':>20} {rb_err_hist[-1]:>18.4e} {ca_err_hist[-1]:>18.4e}")
print(f"  {'Final certificate':>20} {rb_cert_hist[-1]:>18.4e} {ca_cert_hist[-1]:>18.4e}")
print(f"  {'Final effectivity':>20} {rb_cert_hist[-1]/max(rb_err_hist[-1],1e-15):>18.2f} "
      f"{ca_cert_hist[-1]/max(ca_err_hist[-1],1e-15):>18.2f}")
print(f"  {'PDE solves (offline)':>20} {rb_n_hist[-1]:>18} {'(none)':>18}")
print(f"  {'Training samples':>20} {'N/A':>18} {N_tr:>18}")
print(f"  {'Total runtime':>20} {t_rb_end-t_rb:>18.1f}s {t_ca_end-t_ca:>18.1f}s")

# ═══════════════════════════════════════════════════════════════════════════
#  Figures
# ═══════════════════════════════════════════════════════════════════════════

# Fig 1: Convergence comparison
fig, ax = plt.subplots(figsize=(7,5))
ax.semilogy(rb_n_hist, rb_err_hist, 'o-', color='#1f77b4', label='RB error')
ax.semilogy(rb_n_hist, rb_cert_hist, 's--', color='#1f77b4', alpha=0.5, label='RB cert')
ax.semilogy(ca_n_hist, ca_err_hist, 'o-', color='#d62728', label='CAOL error')
ax.semilogy(ca_n_hist, ca_cert_hist, 's--', color='#d62728', alpha=0.5, label='CAOL cert')
ax.set_xlabel('Basis size $n$'); ax.set_ylabel('Error / Certificate')
ax.set_title('RB vs CAOL: Convergence on 2D affine diffusion')
ax.legend(); ax.grid(True, alpha=0.3)
fig.tight_layout(); fig.savefig('figures/fig7_rb_vs_caol.pdf')
print("\n  -> figures/fig7_rb_vs_caol.pdf")

# Fig 2: Effectivity comparison
fig, ax = plt.subplots(figsize=(7,5))
rb_eff = [rb_cert_hist[i]/max(rb_err_hist[i],1e-15) for i in range(len(rb_n_hist))]
ca_eff = [ca_cert_hist[i]/max(ca_err_hist[i],1e-15) for i in range(len(ca_n_hist))]
ax.semilogy(rb_n_hist, rb_eff, 'o-', color='#1f77b4', label='RB')
ax.semilogy(ca_n_hist, ca_eff, 'o-', color='#d62728', label='CAOL')
ax.axhline(1.0, color='gray', ls='--', alpha=0.5)
ax.set_xlabel('Basis size $n$'); ax.set_ylabel('Effectivity $\\eta_n/\\|\\mathcal{G}-\\hat{\\mathcal{G}}_n\\|$')
ax.set_title('Certificate effectivity: RB vs CAOL')
ax.legend(); ax.grid(True, alpha=0.3)
fig.tight_layout(); fig.savefig('figures/fig8_effectivity_comparison.pdf')
print("  -> figures/fig8_effectivity_comparison.pdf")

# ═══════════════════════════════════════════════════════════════════════════
#  Save data
# ═══════════════════════════════════════════════════════════════════════════

np.savez('figures/rb_vs_caol_data.npz',
         rb_n=np.array(rb_n_hist), rb_err=np.array(rb_err_hist),
         rb_cert=np.array(rb_cert_hist),
         ca_n=np.array(ca_n_hist), ca_err=np.array(ca_err_hist),
         ca_cert=np.array(ca_cert_hist),
         alpha=a_coer/a0, beta=beta_est)
print("  Saved figures/rb_vs_caol_data.npz")
print("Done.")
