"""
Scheduler abstraction for the Dead Man's Switch engine.

Current execution path: manual trigger via GET /admin/deadman/scan.

TODO (production — do NOT implement yet):
  1. AWS Lambda: package run_deadman_scan() as a Lambda handler.
     - Runtime: Python 3.12
     - Memory: 256 MB
     - Timeout: 60 s (increase if user base is large)
     - Environment variables: same as backend/.env (inject via SSM Parameter Store)

  2. EventBridge Scheduler: trigger the Lambda daily.
     - Schedule: cron(0 9 * * ? *)   # 09:00 UTC every day
     - Target: the Lambda ARN above
     - IAM: grant the scheduler role lambda:InvokeFunction on the Lambda

  3. IAM for the Lambda execution role:
     - dynamodb:Scan, dynamodb:GetItem, dynamodb:UpdateItem on Aethelgard_Vault
     - logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents

  4. SES / SNS: after marking PENDING_RELEASE, send an email notification to
     the nominee. Add a follow-up Lambda for the actual vault release flow.
"""

from app.services.deadman import scan_dead_man_switch


def run_deadman_scan() -> dict:
    """
    Entry point for manual or scheduled execution.

    Called by:
      - GET /admin/deadman/scan  (manual trigger via admin API)
      - TODO: AWS Lambda handler for the EventBridge Scheduler rule above
    """
    return scan_dead_man_switch()


# ── AWS Lambda handler (future) ───────────────────────────────────────────────
# Uncomment and deploy when EventBridge integration is ready.
#
# def lambda_handler(event: dict, context: object) -> dict:
#     """AWS Lambda entry point invoked by EventBridge Scheduler."""
#     result = run_deadman_scan()
#     print(f"Dead Man's Switch scan complete: {result}")
#     return result
