"""Autonomous Model Maintenance under Concept Drift.

A supervisor for a deployed hourly bike-demand model: it observes delayed
prediction outcomes, detects sustained deterioration, decides whether
retraining is justified, validates candidates, promotes or rejects them and
monitors promoted models for rollback.
"""

__version__ = "0.1.0"
