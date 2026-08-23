#!/usr/bin/env python3
"""scripts/effect_calculator.py — Effect Size & Confidence Interval Calculator.

Pure Python stdlib tool to compute:
- Pooled Standard Deviation (s_pooled)
- Cohen's d
- Hedges' g (exact or small-sample bias corrected)
- Standard Error of g
- 95% Confidence Interval [lower, upper]

Usage:
    python3 scripts/effect_calculator.py --mean1 78.5 --sd1 10.2 --n1 90 --mean2 72.1 --sd2 11.0 --n2 90
"""
from __future__ import annotations

import argparse
import json
import math
import sys


def compute_hedges_g(
    mean1: float, sd1: float, n1: int,
    mean2: float, sd2: float, n2: int
) -> dict:
    if n1 <= 1 or n2 <= 1:
        raise ValueError("Group sample sizes must both be > 1")
    if sd1 <= 0 or sd2 <= 0:
        raise ValueError("Standard deviations must be positive")

    df = n1 + n2 - 2
    # Pooled SD
    s_pooled = math.sqrt(((n1 - 1) * (sd1 ** 2) + (n2 - 1) * (sd2 ** 2)) / df)
    
    # Cohen's d
    d = (mean1 - mean2) / s_pooled
    
    # Hedges' correction factor J(df)
    j = 1.0 - (3.0 / (4.0 * df - 1.0))
    g = j * d
    
    # Variance and Standard Error of g
    var_g = (float(n1 + n2) / (n1 * n2)) + ((g ** 2) / (2.0 * (n1 + n2)))
    se_g = math.sqrt(var_g)
    
    # 95% Confidence Interval (Z_0.975 = 1.95996)
    z_crit = 1.95996398454
    ci_lower = g - z_crit * se_g
    ci_upper = g + z_crit * se_g
    
    # Two-tailed p-value
    z_stat = abs(g / se_g) if se_g > 0 else 0.0
    p_value = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z_stat / math.sqrt(2.0))))

    return {
        "status": "success",
        "cohens_d": round(d, 4),
        "hedges_g": round(g, 4),
        "pooled_sd": round(s_pooled, 4),
        "standard_error": round(se_g, 4),
        "ci_95": [round(ci_lower, 4), round(ci_upper, 4)],
        "p_value": round(p_value, 4),
        "degrees_of_freedom": df,
        "sample_size_total": n1 + n2,
        "sample_size_treatment": n1,
        "sample_size_control": n2,
    }


def main():
    parser = argparse.ArgumentParser(description="Calculate Hedges' g effect size and 95% CI.")
    parser.add_argument("--mean1", type=float, required=True, help="Treatment group mean")
    parser.add_argument("--sd1", type=float, required=True, help="Treatment group standard deviation")
    parser.add_argument("--n1", type=int, required=True, help="Treatment group sample size")
    parser.add_argument("--mean2", type=float, required=True, help="Control group mean")
    parser.add_argument("--sd2", type=float, required=True, help="Control group standard deviation")
    parser.add_argument("--n2", type=int, required=True, help="Control group sample size")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()
    try:
        res = compute_hedges_g(args.mean1, args.sd1, args.n1, args.mean2, args.sd2, args.n2)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("=== Effect Size Calculation Results ===")
            print(f"  • Hedges' g:       {res['hedges_g']} (95% CI: [{res['ci_95'][0]}, {res['ci_95'][1]}])")
            print(f"  • Cohen's d:       {res['cohens_d']}")
            print(f"  • Pooled SD:       {res['pooled_sd']}")
            print(f"  • Standard Error:  {res['standard_error']}")
            print(f"  • p-value:         {res['p_value']}")
            print(f"  • Sample Size:     Treatment N={res['sample_size_treatment']}, Control N={res['sample_size_control']} (Total N={res['sample_size_total']})")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
