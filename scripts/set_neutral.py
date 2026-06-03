"""
set_neutral.py
--------------
Commands all 6 motors to their calibrated neutral position in one shot.

Use this:
    - Before every calibration run — arm needs to start from neutral
    - Before shutting down — parks the arm safely so nothing strains overnight
    - After clearing an overload — get the arm to a safe position before
      restarting teleop
    - After a reboot — confirm motors are responding correctly at neutral

Why this matters:
    The shoulder motor (ID 2) overloads when the arm is extended.
    If you shut down or start teleop with the arm in a bad position,
    the motor immediately fights to reach a position it can't hold.
    Parking at neutral before every session start/end avoids this entirely.

Neutral position = servo unit 2048 (center) for all joints.
This is the physical "arms slightly bent, compact, not extended" position
that was established during calibration.

Usage:
    python scripts/set_neutral.py                     # follower arm
    python scripts/set_neutral.py --port /dev/ttyACM1 # leader arm
    python scripts/set_neutral.py --both              # both arms (two cables needed)
    python scripts/set_neutral.py --slow              # slower movement, safer for first run

Safe neutral positions per joint (from calibration):
    ID 1  base rotation  →  2048
    ID 2  shoulder       →  2048  ← most important
    ID 3  elbow          →  2048
    ID 4  wrist pitch    →  2048
    ID 5  wrist roll     →  2048
    ID 6  gripper        →  2048  (open position)
"""

import argparse
import sys
import time
from scservo_sdk import PortHandler, PacketHandler

BAUDRATE       = 1_000_000
GOAL_POS_ADDR  = 42
NEUTRAL        = 2048

JOINT_NAMES = {
    1: "base rotation",
    2: "shoulder",
    3: "elbow",
    4: "wrist pitch",
    5: "wrist roll",
    6: "gripper",
}


def set_neutral_arm(port_name: str, slow: bool = False):
    port = PortHandler(port_name)
    ph   = PacketHandler(0)

    if not port.openPort():
        print(f"[ERROR] Could not open port {port_name}")
        print("        Run: sudo chmod 666 /dev/ttyACM0")
        return False

    port.setBaudRate(BAUDRATE)
    print(f"\nConnected to {port_name}")

    delay = 0.6 if slow else 0.25

    if slow:
        # slow mode — one joint at a time, safer if arm is in unknown position
        print("Slow mode — moving one joint at a time...\n")
        order = [6, 5, 4, 3, 2, 1]   # gripper first, base last — safer sequence
        for motor_id in order:
            label = JOINT_NAMES.get(motor_id, f"motor {motor_id}")
            ph.write2ByteTxRx(port, motor_id, GOAL_POS_ADDR, NEUTRAL)
            print(f"  → ID {motor_id}  {label}  →  {NEUTRAL}")
            time.sleep(delay)
    else:
        # normal mode — all joints at once
        print("Moving all joints to neutral...\n")
        for motor_id in range(1, 7):
            label = JOINT_NAMES.get(motor_id, f"motor {motor_id}")
            ph.write2ByteTxRx(port, motor_id, GOAL_POS_ADDR, NEUTRAL)
            print(f"  → ID {motor_id}  {label}  →  {NEUTRAL}")
            time.sleep(delay)

    time.sleep(1.5)
    port.closePort()
    print(f"\n[OK]  {port_name} arm at neutral position.")
    return True


def run(port_name: str, both: bool = False, slow: bool = False):
    print("\nLeRobot SO-101 — Set Neutral Position")

    if both:
        print("\nMoving both arms to neutral...")
        set_neutral_arm("/dev/ttyACM0", slow)
        time.sleep(0.5)
        set_neutral_arm("/dev/ttyACM1", slow)
    else:
        set_neutral_arm(port_name, slow)

    print("\nArm(s) parked at neutral. Safe to calibrate, shut down, or start teleop.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Move SO-101 arm(s) to neutral position.")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port (default: /dev/ttyACM0)")
    parser.add_argument("--both", action="store_true", help="Move both arms to neutral")
    parser.add_argument("--slow", action="store_true", help="Move one joint at a time — safer from unknown positions")
    args = parser.parse_args()
    run(args.port, args.both, args.slow)
