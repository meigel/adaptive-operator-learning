#!/usr/bin/env python3
"""
CAOL Experiment 1 — Affine parametric diffusion in 2D
=====================================================
  -∇·(a₀ + Σ y_i √λ_i a_i(x))∇u = 1   on Ω=(0,1)², u=0 on ∂Ω

Operator: polynomial chaos expansion (Legendre), built via proper
weak-greedy enrichment on training data. The certificate uses the
PDE residual measured in V' via the Riesz map (mean stiffness).

Demonstrates: error convergence, reliability, MC certification.
"""

import sys, time, os
import numpy as np
from numpy.polynomial.legendre import legval, legvander
from scipy import sparse as sp
from scipy.sparse.linalg import spsolve, factorized
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from skfem import MeshQuad, ElementQuad1, InteriorBasis, BilinearForm, LinearForm
from skfem import condense
from skfem.helpers import dot, grad

os.makedirs("figures", exist_ok=True)
np.random.seed(42)

# ═══════════════════════════════════════════════════════════════════════════
#  Problem parameters
# ═══════════════════════════════════════════════════════════════════════════

n_mesh  = 25
n_fine  = 45
M_KL    = 8
sigma   = 0.3
a0      = 2.0
f_val   = 1.0

ks      = np.arange(1, M_KL + 1)
lambdas = 1.0 / ks ** 2
α_c = a0 - sigma * np.sqrt((lambdas).sum())
assert α_c > 0, "Coercivity violated!"

print("=" * 62)
print("  CAOL Experiment 1 — Corrected greedy enrichment")
print("=" * 62)
print(f"  Mesh {n_mesh}×{n_mesh} / {n_fine}×{n_fine}, DOFs {n_mesh**2}")
print(f"  KL M={M_KL}, σ={sigma}, a₀={a0}, α≥{α_c:.4f}")

# ═══════════════════════════════════════════════════════════════════════════
#  FEM
# ═══════════════════════════════════════════════════════════════════════════

@BilinearForm
def diffusion(u, v, w):
    return w.a * dot(grad(u), grad(v))

@LinearForm
def load(v, w):
    return f_val * v

mesh = MeshQuad.init_tensor(np.linspace(0,1,n_mesh), np.linspace(0,1,n_mesh))
basis = InteriorBasis(mesh, ElementQuad1(), intorder=3)
D = basis.get_dofs(lambda x: (x[0]==0)|(x[0]==1)|(x[1]==0)|(x[1]==1))
N = basis.N

mesh_fine = MeshQuad.init_tensor(np.linspace(0,1,n_fine), np.linspace(0,1,n_fine))
basis_fine = InteriorBasis(mesh_fine, ElementQuad1(), intorder=3)
D_fine = basis_fine.get_dofs(lambda x: (x[0]==0)|(x[0]==1)|(x[1]==0)|(x[1]==1))

b_fixed = load.assemble(basis)
K0_mat = diffusion.assemble(basis, a=np.ones(N)*a0)
_, _, _, interior = condense(K0_mat, b_fixed, D=D)
K0_int = K0_mat[interior][:, interior]
K0_fact = factorized(K0_int.tocsc())
b_int = b_fixed[interior]

# Precomputed KL matrices on interior
kl_int = []
for k in ks:
    @BilinearForm
    def kl_fn(u, v, w, kk=k):
        return (np.sin(np.pi*kk*w.x[0])*np.sin(np.pi*kk*w.x[1])
                * dot(grad(u), grad(v)))
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
#  Polynomial Operator + Weak-Greedy Enrichment
# ═══════════════════════════════════════════════════════════════════════════

class PolyOp:
    """Ĝ_n(y) = Σ_j c_j · m_j(y) where m_j(y) are monomials in y."""
    def __init__(self, M):
        self.M = M
        self.coeffs = []      # list of (alpha, c_vec) pairs
        self.n = 0

    def eval(self, y):
        u = np.zeros(N)
        for alpha, c in self.coeffs:
            psi = 1.0
            for d in range(self.M):
                ei = [0]*(alpha[d]+1); ei[alpha[d]]=1
                psi *= legval(y[d], ei)
            u += psi * c
        return u

    def add(self, alpha, c):
        self.coeffs.append((alpha, c))
        self.n += 1

# Generate all multi-indices up to given max degree
def all_indices(M, max_deg):
    idx = []
    for total in range(max_deg+1):
        def gen(d, rem, cur):
            if d==1:
                idx.append(tuple(cur+[rem]))
            else:
                for v in range(rem+1):
                    gen(d-1, rem-v, cur+[v])
        gen(M, total, [])
    return idx

# Greedy enrichment: at each step, try every candidate α not yet in the basis.
# For each α, compute the optimal coefficient vector c_α by solving
# a least-squares problem on training data in the V-norm.
# Select α that gives the biggest V-norm error reduction.

def greedy_enrich(op, train_y, train_u, candidates):
    """
    One step of weak-greedy enrichment.
    Returns True if a new term was added.
    """
    n_tr = len(train_y)
    best_α = None
    best_c = None
    best_red = -np.inf

    # Precompute current residuals in V-norm terms
    # For least-squares: for each α, we want c_α that minimises
    # Σ_i ||e_i - Ψ_α(y_i)·c||_V² where e_i = u(y_i) - ĝ_n(y_i)
    # The solution is: c = (Σ Ψ_i²)^{-1} · Σ Ψ_i · e_i

    for α in candidates:
        if any(α == a for a, _ in op.coeffs):
            continue

        # Compute Ψ_α(y_i) for all training samples
        psi = np.ones(n_tr)
        for d in range(op.M):
            for i in range(n_tr):
                ei = [0]*(α[d]+1); ei[α[d]]=1
                psi[i] *= legval(train_y[i][d], ei)

        # Compute numerator: Σ Ψ_i · e_i  (elementwise in space)
        # and denominator: Σ Ψ_i²
        num = np.zeros(N)
        den = 0.0
        for i in range(n_tr):
            e_i = train_u[i] - op.eval(train_y[i])
            num += psi[i] * e_i
            den += psi[i]**2

        if den < 1e-14:
            continue

        # c = num / den
        c = num / den

        # Compute reduction in V-norm error
        red = 0.0
        for i in range(n_tr):
            err_old = train_u[i] - op.eval(train_y[i])
            err_new = err_old - psi[i] * c
            red += v_norm_sq(err_old) - v_norm_sq(err_new)

        if red > best_red:
            best_red = red
            best_α = α
            best_c = c

    if best_α is not None and best_red > 1e-14:
        op.add(best_α, best_c)
        return True
    return False

# ═══════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════

print("\nGenerating samples...")
t0 = time.perf_counter()
N_tr = 200
train_y = [np.random.uniform(-1,1,M_KL) for _ in range(N_tr)]
train_u = [solve_pde(y) for y in train_y]
N_te = 100
test_y  = [np.random.uniform(-1,1,M_KL) for _ in range(N_te)]
test_u  = [solve_pde(y) for y in test_y]
print(f"  {N_tr} train + {N_te} test ({time.perf_counter()-t0:.1f}s)")

candidates = all_indices(M_KL, 3)
# Remove (0,...,0) — it's the first term we add
candidates = [c for c in candidates if any(cd > 0 for cd in c)]
print(f"  Candidate pool (deg 1-3): {len(candidates)}")
print()

op = PolyOp(M_KL)

# Step 0: add the mean solution (α = 0)
u_mean = np.mean(train_u, axis=0)
op.add(tuple([0]*M_KL), u_mean)

M_MC = 200
max_steps = 60
n_hist, err_hist, cert_hist, eff_hist = [], [], [], []

print("Adaptive enrichment:")
t_start = time.perf_counter()

for step in range(max_steps):
    t_step = time.perf_counter()

    # L²_μ V-norm error on test set
    err_sq = 0.0
    for i in range(N_te):
        err_sq += v_norm_sq(test_u[i] - op.eval(test_y[i]))
    err = np.sqrt(err_sq / N_te)

    # MC certificate
    cert_sq = 0.0
    for _ in range(M_MC):
        y = np.random.uniform(-1,1,M_KL)
        cert_sq += residual_Vprime_norm(y, op.eval(y))**2
    cert = np.sqrt(cert_sq / M_MC)

    eff = cert / max(err, 1e-15)

    n_hist.append(op.n); err_hist.append(err)
    cert_hist.append(cert); eff_hist.append(eff)

    print(f"  Step {step:2d} n={op.n:2d} | err_V={err:.4e} | cert={cert:.4e} | eff={eff:.2f} "
          f"({time.perf_counter()-t_step:.1f}s)")

    if err < 1e-5 or op.n >= 100:
        break

    ok = greedy_enrich(op, train_y, train_u, candidates)
    if not ok:
        print("  No further enrichment possible")
        break

print(f"  Total: {time.perf_counter()-t_start:.1f}s")

# ── MC convergence ─────────────────────────────────────────────────────
print("\nMC convergence...")
M_ref = 2000
cs = 0.0
for _ in range(M_ref):
    y = np.random.uniform(-1,1,M_KL)
    cs += residual_Vprime_norm(y, op.eval(y))**2
eta_ref = np.sqrt(cs / M_ref)
print(f"  η_ref (M={M_ref}): {eta_ref:.4e}")

M_range = [10,25,50,100,200,500]
mc_errors = []
for M in M_range:
    e = []
    for _ in range(30):
        cs = 0.0
        for _ in range(M):
            y = np.random.uniform(-1,1,M_KL)
            cs += residual_Vprime_norm(y, op.eval(y))**2
        e.append(abs(np.sqrt(cs/M) - eta_ref))
    mc_errors.append(np.mean(e))
    print(f"  M={M:4d}  |η−η̂|={mc_errors[-1]:.4e}  O(M^-1/2)={eta_ref/np.sqrt(M):.4e}")

# ═══════════════════════════════════════════════════════════════════════════
#  Figures
# ═══════════════════════════════════════════════════════════════════════════

n_arr = np.array(n_hist)[:len(err_hist)]
err_arr = np.array(err_hist)
cert_arr = np.array(cert_hist)
eff_arr = np.array(eff_hist)

plt.rcParams['text.usetex'] = False  # avoid missing glyphs

# Fig 1: Error + certificate
fig, ax = plt.subplots(figsize=(6,4))
ax.semilogy(n_arr, err_arr, 'o-', color='#1f77b4', label='Error $\\|\\mathcal{G}-\\hat{\\mathcal{G}}_n\\|$')
ax.semilogy(n_arr, cert_arr, 's--', color='#d62728', label='Certificate $\\eta_n$')
ax.set_xlabel('Number of terms $n$'); ax.set_ylabel('Error / Certificate')
ax.set_title('Adaptive enrichment: error and certificate')
ax.legend(); ax.grid(True, alpha=0.3)
fig.tight_layout(); fig.savefig('figures/fig1_error_convergence.pdf')
print("  -> figures/fig1_error_convergence.pdf")

# Fig 2: Effectivity
fig, ax = plt.subplots(figsize=(6,4))
ax.semilogy(n_arr, eff_arr, 'o-', color='#2ca02c')
ax.axhline(1.0, color='gray', ls='--', alpha=0.5)
ax.set_xlabel('$n$'); ax.set_ylabel('Effectivity $\\eta_n / \\|\\mathcal{G}-\\hat{\\mathcal{G}}_n\\|$')
ax.set_title('Certificate effectivity'); ax.grid(True, alpha=0.3)
fig.tight_layout(); fig.savefig('figures/fig2_effectivity.pdf')
print("  -> figures/fig2_effectivity.pdf")

# Fig 3: Reliability — cert vs error
fig, ax = plt.subplots(figsize=(6,4))
ax.loglog(err_arr, cert_arr, 'o-', color='#ff7f0e')
ax.loglog(err_arr, err_arr, '--', color='gray', alpha=0.5, label='$y=x$')
ax.set_xlabel('True error $\\|\\mathcal{G}-\\hat{\\mathcal{G}}_n\\|$')
ax.set_ylabel('Certificate $\\eta_n$')
ax.set_title('Reliability: certificate vs error')
ax.legend(); ax.grid(True, alpha=0.3)
fig.tight_layout(); fig.savefig('figures/fig3_reliability.pdf')
print("  -> figures/fig3_reliability.pdf")

# Fig 4: MC convergence
fig, ax = plt.subplots(figsize=(6,4))
ax.loglog(M_range, mc_errors, 'o-', color='#9467bd', label='$|\\eta - \\hat{\\eta}|$')
ax.loglog(M_range, mc_errors[0]*(M_range[0]/np.array(M_range))**0.5,
          '--', color='gray', label='$O(M^{-1/2})$')
ax.set_xlabel('MC samples $M$'); ax.set_ylabel('MC estimation error')
ax.set_title('Monte Carlo certification'); ax.legend(); ax.grid(True, alpha=0.3)
fig.tight_layout(); fig.savefig('figures/fig4_mc_convergence.pdf')
print("  -> figures/fig4_mc_convergence.pdf")

# ═══════════════════════════════════════════════════════════════════════════
#  Summary
# ═══════════════════════════════════════════════════════════════════════════

print("\n" + "="*62)
print("  Summary")
print("="*62)
print(f"  Final terms:      {op.n}")
print(f"  Final error:      {err_hist[-1]:.4e}")
print(f"  Final certificate: {cert_hist[-1]:.4e}")
print(f"  Final effectivity: {eff_hist[-1]:.2f}")
print(f"  α·error at final: {α_c*err_hist[-1]:.4e}")
print(f"  cert·α / error?   {cert_hist[-1]/α_c/err_hist[-1]:.2f}, cert≥α·err? {cert_hist[-1] >= α_c*err_hist[-1]}")
print(f"  MC ref η:         {eta_ref:.4e}")
print(f"  Used indices:     {[a for a,_ in op.coeffs]}")
print()

np.savez('figures/experiment_data.npz',
         n_arr=n_arr, err_arr=err_arr, cert_arr=cert_arr,
         eff_arr=eff_arr, M_arr=np.array(M_range), mc_errors=mc_errors)
print("  Saved figures/experiment_data.npz")
print("Done.")
