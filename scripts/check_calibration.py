"""
check_calibration.py
--------------------
Reads the saved calibration JSON files and prints a clean summary of every
joint's homing offset, min/max range, and current state.

Before this script existed, inspecting calibration meant manually opening
the JSON file and reading raw numbers with no context. This makes it one
command — run it after every calibration to verify the values look sane
before you trust them in a teleoperation session.

Run this especially if:
    - The arm jumps to a wrong position on startup
    - A joint feels like it's fighting its neutral position
    - You suspect the calibration file has wrong offsets
    - After any redo of calibration — verify before running teleop

Usage:
    python scripts/check_calibration.py                    # both arms
    python scripts/check_calibration.py --arm follower     # follower only
    python scripts/check_calibration.py --arm leader       # leader only

Calibration file locations:
    follower  ->  ~/.cache/huggingface/lerobot/calibration/robots/so_follower/None.json
    leader    ->  ~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/None.json
"""

import argparse
import json
import os
from pathlib import Path

CACHE_BASE = Path.home() / ".cache" / "huggingface" / "lerobot" / "calibration"

CALIBRATION_PATHS = {
    "follower": CACHE_BASE / "robots" / "so_follower" / "None.json",
    "leader":   CACHE_BASE / "teleoperators" / "so_leader" / "None.json",
}

JOINT_NAMES = {
    0: "base rotation",
    1: "shoulder       ← overload risk if offset wrong",
    2: "elbow",
    3: "wrist pitch",
    4: "wrist roll",
    5: "gripper",
}

# Thresholds — offsets outside this range are suspicious
OFFSET_WARN_RANGE = (-2000, 2000)
RANGE_MIN_WIDTH   = 500   # if max - min is less than this, something is wrong


def check_arm(arm_name: str, path: Path):
    print(f"\n{'━' * 50}")
    print(f"  {arm_name.upper()} ARM")
    print(f"  {path}")
    print(f"{'━' * 50}")

    if not path.exists():
        print(f"\n  [ERROR] Calibration file not found.")
        print(f"          Run calibration first:")
        if arm_name == "follower":
            print(f"          python src/lerobot/scripts/lerobot_calibrate.py \\")
            print(f"            --robot.type=so101_follower --robot.port=/dev/ttyACM0")
        else:
            print(f"          python src/lerobot/scripts/lerobot_calibrate.py \\")
            print(f"            --teleop.type=so101_leader --teleop.port=/dev/ttyACM1")
        return

    with open(path) as f:
        data = json.load(f)

    # Handle both list and dict formats LeRobot may save
    if isinstance(data, dict):
        joints = data
    elif isinstance(data, list):
        joints = {str(i): v for i, v in enumerate(data)}
    else:
        print(f"  [ERROR] Unexpected calibration format: {type(data)}")
        return

    warnings = []

    print(f"\n  {'ID':<4} {'Joint':<42} {'Offset':>8}  {'Min':>6}  {'Max':>6}  {'Range':>6}")
    print(f"  {'-'*4} {'-'*42} {'-'*8}  {'-'*6}  {'-'*6}  {'-'*6}")

    for idx, (key, joint_data) in enumerate(joints.items()):
        if isinstance(joint_data, dict):
            offset   = joint_data.get("homing_offset", joint_data.get("offset", "N/A"))
            min_pos  = joint_data.get("range_min",     joint_data.get("min", "N/A"))
            max_pos  = joint_data.get("range_max",     joint_data.get("max", "N/A"))
        else:
            offset, min_pos, max_pos = "N/A", "N/A", "N/A"

        label = JOINT_NAMES.get(idx, f"joint {idx}")

        # calculate range
        range_width = "N/A"
        if isinstance(min_pos, (int, float)) and isinstance(max_pos, (int, float)):
            range_width = int(max_pos - min_pos)

        # flag warnings
        flag = ""
        if isinstance(offset, (int, float)):
            if not (OFFSET_WARN_RANGE[0] <= offset <= OFFSET_WARN_RANGE[1]):
                flag = " ⚠️  offset out of normal range"
                warnings.append(f"ID {idx+1} ({label.split()[0]}): offset {offset} is outside [{OFFSET_WARN_RANGE[0]}, {OFFSET_WARN_RANGE[1]}]")
        if isinstance(range_width, int) and range_width < RANGE_MIN_WIDTH:
            flag = " ⚠️  range too narrow — recalibrate"
            warnings.append(f"ID {idx+1} ({label.split()[0]}): range {range_width} is suspiciously narrow")

        print(f"  {idx+1:<4} {label:<42} {str(offset):>8}  {str(min_pos):>6}  {str(max_pos):>6}  {str(range_width):>6}{flag}")

    if warnings:
        print(f"\n  ⚠️  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"     - {w}")
        print(f"\n     These joints may cause overload or wrong positioning.")
        print(f"     Recommendation: redo calibration for the flagged joints.")
    else:
        print(f"\n  ✓  All offsets and ranges look normal.")


def main(arm: str = "both"):
    print("\nLeRobot SO-101 — Calibration Check")

    if arm in ("both", "follower"):
        check_arm("follower", CALIBRATION_PATHS["follower"])

    if arm in ("both", "leader"):
        check_arm("leader", CALIBRATION_PATHS["leader"])

    print(f"\n{'━' * 50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check SO-101 calibration files and flag suspicious values.")
    parser.add_argument("--arm", choices=["follower", "leader", "both"], default="both",
                        help="Which arm to check (default: both)")
    args = parser.parse_args()
    main(args.arm)
