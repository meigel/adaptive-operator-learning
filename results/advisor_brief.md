# Certified Adaptive Operator Learning — Advisor Brief

## Project Context

We are starting a paper on "Certified Adaptive Operator Learning" — a framework for
learning PDE solution operators with computable, statistically certified error estimates
and adaptive enrichment.

Two documents exist:
- `research-plan.md`: The broad vision — CAOL unifying AFEM, RB, SGFEM, neural operators,
  tensor operators. Proposes 6 objectives, 5 theorems, 6 work packages over 36 months.
- `paper-plan.md`: A sharp critique — argues the broad vision is too much for one paper.
  Proposes stripping back to affine-parametric uniformly coercive operators only.
  The genuinely new theorem is Theorem 4: "Certified Weak-Greedy Operator Learning."

## The Central Tension

The research-plan defines everything by operator manifold widths (Kolmogorov widths)
for architecture-independence — then shows TT, CTT, DeepONet, etc. realize those widths.
The paper-plan says: for Paper 1, drop all architectures, drop nonlinear PDEs, drop
lognormal coefficients. Prove the certification+adaptivity result in the simplest
nontrivial setting. Paper 2 gets architecture-specific rates. Paper 3 gets nonlinearity.

**Key question**: Should Paper 1 be the stripped-back version (paper-plan),
or should we try to include architecture-specific rates in a single paper?

## Problem Setting (Paper 1 — stripped version)

A_y(u) = f_y,  y ∈ U ⊂ ℝ^∞,
with uniformly coercive affine-parametric operators:
  a_y(v, v) ≥ α ‖v‖_V².

Solution operator: G(y) = u(y).
Approximation: Ĝ_n(y).

## The Theorem Sequence (Paper 1, per paper-plan)

**Theorem 1 (Operator Reliability)**: ‖G - Ĝ_n‖_{L²_μ(U;V)} ≤ α⁻¹ η_n,
where η_n² = ∫_U ‖R_n(y)‖_{V'}^2 dμ(y), R_n(y) = f_y - A_y(Ĝ_n(y)).

(Straightforward — coercivity + Cauchy-Schwarz.)

**Theorem 2 (Statistical Certification)**:
Pr(|η_n² - Ŝ_n²| > ε) ≤ 2 exp(-2Mε²/B²).
Hence η_n ≤ Ŝ_n + O(M^{-½}) with high probability.

**Theorem 3 (Width-Based Rate)**:
If d_n(M)_V ≤ C n^{-s} (Kolmogorov widths of M = G(U)),
and adaptive enrichment is weak-greedy, then
‖G - Ĝ_n‖ ≤ C' n^{-s}.
Follows from BCDDPW-type weak-greedy theory.

**Theorem 4 (Certified Weak-Greedy Operator Learning)**:
Combine 1-3: under coercivity + weak-greedy + MC certification
with |η_n - Ŝ_n| ≤ δ_n, ∑δ_n < ∞, we get
‖G - Ĝ_n‖ ≤ C n^{-s} + C ∑_{k≥n} δ_k.
This is the genuinely new theorem — combines widths + greedy + statistical certification.

## Strategic Questions

1. **Paper 1 scope**: Should the first paper be the stripped-back version (coercive
   affine-parametric only, no architecture-specific rates, Theorem 4 as headline)?
   Or should we attempt to include architecture-specific classes (TT, DeepONet) and
   aim for a longer, more comprehensive paper?

2. **Headline theorem**: Is Theorem 4 genuinely new as framed? Or does some combination
   of existing results (e.g., Cohen-Devore-Schwab 2000s greedy approximation + Hoeffding)
   already cover this territory? What is the sharpest way to position novelty?

3. **Width-based vs architecture-specific**: The paper-plan uses Kolmogorov widths
   (d_n(M)_V) as the approximation class, deferring architecture-specific realization
   theorems to Paper 2. Is this defensible, or will reviewers demand "give me an
   actual algorithm that achieves n^{-s}"?

4. **Gap in the chain**: The reliability theorem (T1) bounds error in V-norm.
   The width assumption is also in V-norm. The MC concentration needs V'-norm
   bounds on the residual. Is the V ↔ V' duality gap problematic here?
   We have R_n(y) = A_y(e(y)) where A_y: V→V'. The reliability bound uses
   V'-norm of residual to bound V-norm of error. The MC samples need bounded
   ‖R_n(y)‖_{V'}^2 ≤ B. Can we bound B in terms of known quantities
   (coercivity, continuity, f, Ĝ_n)?

5. **Comparison to AFEM optimality**: Theorem 4 is presented as the "operator-learning
   analogue of AFEM optimality." Is this the right comparison class, or should we
   be comparing to reduced basis methods (which also have greedy enrichment +
   residual-based certification)?

6. **Paper 1 timeline**: Assuming the stripped-back scope, what is the minimum
   experiment battery needed? A single parametric diffusion benchmark (affine KL,
   2D spatial domain, moderate KL terms M≈20) with TT operator approximation?
   Or do we need a second architecture (e.g., neural operator) to claim
   architecture-independence?

## Files

- paper-plan.md (full content, project root)
- research-plan.md (full content, project root)
- tex/ (new directory for paper)
- src/ (new directory for implementation)
