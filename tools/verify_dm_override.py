#!/usr/bin/env python3
"""Verify the DM override in policy.py without importing openpilot.

Imports would need cereal bindings and a built openpilot. Instead this parses the class
body and takes the LAST assignment for each name — which is precisely how Python executes
the __init__: the override block at the end wins over the defaults above it.

It then reproduces the escalation maths from policy.py to report, in seconds, when each
alert level fires under sustained distraction.
"""

import ast
import sys
from pathlib import Path

NAMES = [
  "_VISION_POLICY_ALERT_1_TIMEOUT", "_VISION_POLICY_ALERT_2_TIMEOUT",
  "_VISION_POLICY_ALERT_3_TIMEOUT", "_PHONE_THRESH", "_DISTRACTED_FILTER_TS",
  "_POSE_PITCH_THRESHOLD", "_POSE_YAW_THRESHOLD", "_PITCH_NATURAL_THRESHOLD",
  "_MAX_ALERT_3", "_MAX_NO_RESPONSE", "_BLINK_THRESHOLD", "_WHEELTOUCH_POLICY_ALERT_1_TIMEOUT", "_WHEELTOUCH_POLICY_ALERT_2_TIMEOUT", "_WHEELTOUCH_POLICY_ALERT_3_TIMEOUT",
]

DEFAULTS = {  # what upstream ships, for the before/after table
  "_VISION_POLICY_ALERT_1_TIMEOUT": 5.0, "_VISION_POLICY_ALERT_2_TIMEOUT": 8.0,
  "_VISION_POLICY_ALERT_3_TIMEOUT": 13.0, "_PHONE_THRESH": 0.5,
  "_DISTRACTED_FILTER_TS": 0.25, "_POSE_PITCH_THRESHOLD": 0.3133,
  "_POSE_YAW_THRESHOLD": 0.4020, "_PITCH_NATURAL_THRESHOLD": 0.449,
  "_MAX_ALERT_3": 2, "_MAX_NO_RESPONSE": 1, "_BLINK_THRESHOLD": 0.865,
  "_WHEELTOUCH_POLICY_ALERT_1_TIMEOUT": 5.0, "_WHEELTOUCH_POLICY_ALERT_2_TIMEOUT": 15.0,
  "_WHEELTOUCH_POLICY_ALERT_3_TIMEOUT": 25.0,
}


def effective_values(path: Path):
  tree = ast.parse(path.read_text())
  vals = {}
  for node in ast.walk(tree):
    if not isinstance(node, ast.ClassDef) or node.name != "DRIVER_MONITOR_SETTINGS":
      continue
    for item in node.body:
      if not isinstance(item, ast.FunctionDef) or item.name != "__init__":
        continue
      for stmt in item.body:
        if not isinstance(stmt, ast.Assign):
          continue
        for tgt in stmt.targets:
          if isinstance(tgt, ast.Attribute) and tgt.attr in NAMES:
            try:
              vals[tgt.attr] = ast.literal_eval(stmt.value)
            except ValueError:
              pass  # e.g. self._POSE_PITCH_THRESHOLD_STRICT = self._POS...
  return vals


def main() -> int:
  path = Path(sys.argv[1])
  got = effective_values(path)
  missing = [n for n in NAMES if n not in got]
  if missing:
    print(f"MISSING (never assigned): {missing}", file=sys.stderr)

  print(f"{'setting':38} {'upstream':>10} {'effective':>10}  changed")
  for n in NAMES:
    up, cur = DEFAULTS.get(n), got.get(n)
    mark = "" if up is None or cur is None or up == cur else "<-- changed"
    print(f"{n:38} {str(up):>10} {str(cur):>10}  {mark}")

  t1, t2, t3 = (got[n] for n in
                ("_VISION_POLICY_ALERT_1_TIMEOUT", "_VISION_POLICY_ALERT_2_TIMEOUT",
                 "_VISION_POLICY_ALERT_3_TIMEOUT"))
  th1 = 1.0 - t1 / t3
  th2 = 1.0 - t2 / t3
  print("\nEscalation under sustained distraction (vision policy):")
  print(f"  alert_1 (gentle) at ~{t1:.0f}s   (awareness <= {th1:.3f})")
  print(f"  alert_2 (orange) at ~{t2:.0f}s   (awareness <= {th2:.3f})")
  print(f"  alert_3 (red)    at ~{t3:.0f}s   (awareness <= 0)")
  up = DEFAULTS
  print(f"  upstream was:    {up['_VISION_POLICY_ALERT_1_TIMEOUT']:.0f}s / "
        f"{up['_VISION_POLICY_ALERT_2_TIMEOUT']:.0f}s / "
        f"{up['_VISION_POLICY_ALERT_3_TIMEOUT']:.0f}s")
  print(f"  grace multiplier: {t3 / up['_VISION_POLICY_ALERT_3_TIMEOUT']:.2f}x before red")

  # sanity: the strict/non-strict aliases must agree, or the pose check diverges
  src = path.read_text()
  if "_POSE_PITCH_THRESHOLD_STRICT = self._POSE_PITCH_THRESHOLD" not in src:
    print("\nWARNING: STRICT pitch alias not tied to the relaxed value", file=sys.stderr)
  return 0


if __name__ == "__main__":
  sys.exit(main())
