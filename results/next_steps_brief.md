# CAOL Next Steps — Advisor Brief

## Current state of the paper

15-page manuscript, compiles clean, with:

**Theory (4 theorems, 2 lemmas):**
- Lemma 1 (Reliability): ||G - Ĝ_n||_L²_μ(V) ≤ α⁻¹ η_n
- Theorem 3 (Weak-greedy rate): under width decay d_n ≤ C n^{-s}, weak-greedy → rate n^{-s}
- Lemma 2 (MC concentration): |η_n - Ŝ_n| ≤ O(M^{-1/2}) w.h.p.
- Theorem 1 (Certified weak-greedy): ||G - Ĝ_n|| ≤ C n^{-s} + C Σ δ_k
- Theorem 2 (Algorithm convergence)
- RB comparison subsection (§4.3)

**Experiments:**
- E1 (Baseline): 2D affine diffusion, 8 KL, k⁻² decay, polynomial chaos operator.
  Error drops 1.55e-2 → 2.03e-3 (7.5×), cert tracks error at effectivity 0.87-1.0,
  MC follows O(M^{-1/2}), B (max residual) ≈ 6× cert²
- E2 (Negative): k^{-0.5} decay, σ=1.0. Error stalls at 1.8× reduction,
  MC error 8.7× larger, but cert still reliable (effectivity ~0.8)

**Architecture:** Polynomial chaos (Legendre) operator with weak-greedy enrichment.
The paper claims architecture-independence but only demonstrates one architecture.

## Key strategic questions

1. **What architecture for Paper 1?** Currently: polynomial chaos (gPC). The paper claims
   architecture-independence. Options:
   (a) Keep gPC — simple, clean, rigorous
   (b) Add TT operator — more impressive, shows architecture-independence claim is real
   (c) Add a small neural operator (MLP-based) — shows true black-box architecture works

2. **Efficiency bound?** Currently only reliability. An efficiency bound η_n ≥ C ||G - Ĝ_n||
   would give a two-sided certificate. Is this feasible for the affine-parametric case?

3. **Nonlinear operators?** Paper 3 material or fold into Paper 1 for stronger claim?
   Monotone operator theory gives ||u - û|| ≤ C ||R||_{V'} under strong monotonicity.

4. **Lognormal coefficients?** Currently affine-parametric only. Lognormal = unbounded
   parameters, needs different analysis. Major extension or separate paper?

5. **Experiment impact:** What single experiment would most strengthen the paper?
   (a) TT operator showing same framework works — demonstrates architecture-independence
   (b) Higher-dimensional parameter space (p=50) — shows scalability
   (c) Non-affine coefficient — breaks the offline-online paradigm, motivates MC cert
   (d) Comparison to RB on the same problem — demonstrates advantage

6. **Target journal:** SINUM (traditional, rigorous), FoCM (modern, algorithmic),
   Numerische Mathematik, ESAIM:M2AN, or Computer Methods in Applied Mechanics?

7. **Reviewer vulnerability:** What's the weakest point a sharp referee will attack?
