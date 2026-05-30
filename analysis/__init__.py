"""
analysis/ — Price anomaly detection and statistical analysis for AgriFlow.

This package is intentionally dependency-light: numpy + stdlib csv only.
No pandas, no statsmodels, no sklearn.  Results are interpretable by
construction — every flagged point shows the rolling median it deviated from
and the exact percentage deviation.
"""
