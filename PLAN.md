# Strategic Synthesis — CAOL Paper 1

## Convergences (All Three Advisors Agree)

| Point | Consensus | Strength |
|-------|-----------|----------|
| **Scope: stripped-back** | Paper 1 = affine-parametric coercive only. No DeepONet/FNO/CTT. | STRONG — unanimous |
| **Theorem 4 novelty** | New as synthesis, not as individual steps. The MC certification layer is the genuinely new component, not the weak-greedy + width combination (which is RB theory). | STRONG — unanimous |
| **RB comparison is critical** | A dedicated comparison with reduced basis methods is essential. A reviewer from RB community will otherwise reject. | STRONG — unanimous |
| **Width-based approach** | Defensible as an input assumption, but needs explicit citation of Cohen-Devore-Schwab for width decay in affine-parametric case. | STRONG — unanimous |
| **V↔V' duality gap** | Must be explicitly addressed. The V' norm computation requires either Riesz map solving (separable-form assumption) or a discrete proxy with error analysis. | STRONG — unanimous |

## Tensions

| Issue | Codex | CC | AGY |
|-------|-------|----|-----|
| **Primary comparison class** | AFEM optimality (primary), RB (secondary) | AFEM + RB comparison table | RB is THE comparison — not fully addressing it is the biggest vulnerability |
| **Theorem count** | 4 theorems fine | Compress to 2 (combine T3+T4, T1+T2 become lemmas) | Implicitly agrees with CC |
| **Experiment battery** | 3 benchmarks (1D→2D→singularity), ~8 figures | 1 benchmark, 3 figures | Add a negative experiment (slow KL decay → certificate fails) |
| **V' norm solution** | Separable-form assumption → Riesz map solves it | Not flagged heavily | Deep concern — claims it's the #1 reviewer attack point |

## Resolution

1. **Theorem count**: Adopt CC's 2-theorem structure + AGY's "third path" (architecture-independence as framing principle, not theorem). Theorem 1 = Certified Weak-Greedy Operator Approximation (combining old T3+T4 with reliability+MC as lemmas). Theorem 2 = Convergence of the adaptive algorithm.

2. **RB comparison**: Adopt AGY's strongest framing — dedicate a full subsection "Relationship to Reduced Basis Methods" with a structured comparison table. Primary narrative: "AFEM for operators" (Codex's framing) but with RB as the explicit predecessor that we extend in specific directions (Bochner norm, statistical certification, architecture-agnostic).

3. **V' norm**: Address explicitly. State the separable-form assumption (Ĝ_n = ∑ c_j(y) ϕ_j(x)), which makes the V' norm computable via Riesz map — exactly the RB methodology but with learned coefficients. Acknowledge that black-box neural operators would need additional analysis (Paper 2/3).

4. **Experiments**: 1 primary benchmark (2D affine diffusion, M≈20 KL terms, TT operator), 3 core figures (rate convergence, adaptive vs uniform, MC certificate accuracy). Include a brief discussion of the failure regime (slow KL decay → loose certificate) as AGY suggests — this demonstrates intellectual honesty.

## Paper Plan (adopted)

### Title
Residual-Based Certification and Adaptive Approximation of Solution Operators
(or "Certified Adaptive Operator Learning for Parametric Elliptic PDEs")

### Structure (2-theorem version)

1. Introduction — set up the gap (AFEM has certification, operator learning doesn't; RB partially does but limited)
2. Problem setting — abstract operator, coercivity, Bochner spaces
3. Operator residual certification
   - 3.1 Reliability estimate (Lemma 1)
   - 3.2 Weak-greedy operator approximation
   - 3.3 Statistical residual estimation (Lemma 2)
   - 3.4 Theorem 1: Certified weak-greedy operator approximation
4. Adaptive algorithm and convergence
   - 4.1 Algorithm description
   - 4.2 Theorem 2: Convergence and rates
   - 4.3 Relationship to reduced basis methods
5. Numerical experiments
6. Discussion and outlook
