# src/ — Implementation

This directory contains the implementation of the certified adaptive operator
learning (CAOL) framework for affine-parametric coercive PDEs.

## Planned structure

- `operators/` — PDE operator classes (affine diffusion, etc.)
- `approximation/` — operator approximation architectures (TT, polynomial, etc.)
- `certification/` — residual estimation, MC sampling, weak-greedy enrichment
- `experiments/` — experiment scripts and configs
- `utils/` — FE assembly, quadrature, basis functions

## Dependencies

- Python 3.11+ with numpy, scipy, matplotlib
- tinyTT or tntorch for tensor-train operations
- FEniCS or scikit-fem for FE discretization
