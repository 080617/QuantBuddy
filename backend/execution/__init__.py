"""Qlib-to-Futu planning and explicitly gated simulated-canary execution.

Importing this package is inert. The only write path is the interactive,
one-order/one-lot CN SIMULATE canary command guarded by two environment flags.
"""

from .models import ExecutionArtifact, ExecutionPlan, PlanningConfig

__all__ = ["ExecutionArtifact", "ExecutionPlan", "PlanningConfig"]
