"""
clear_overload.py
-----------------
Clears the overload error on the shoulder motor (ID 2).

Motor ID 2 (shoulder) throws an overload error when the arm is held in a
fully extended position. The motor struggles against the arm's weight and
trips its protection flag. Teleoperation stops responding until cleared.

This happened to us repeatedly until we learned to keep the arm compact
during teleoperation — elbow bent, not fully outstretched.

Usage:
    python scripts/clear_overload.py              # clears ID 2 (shoulder)
    python scripts/clear_overload.py --id 3       # clear any motor by ID
    python scripts/clear_overload.py --all        # clear all 6 motors
    python scripts/clear_overload.py --port /dev/ttyACM1  # leader arm

When to run this:
    - Teleoperation freezes mid-session
    - Terminal shows "Overload error on motor ID X"
    - Arm goes limp on one joint

After clearing:
    - Don't just restart teleoperation immediately
    - Manually move the arm to a compact neutral position first
    - Then restart — the overload will retrigger if you start extended again
"""

import argparse
import sys
import time
from scservo_sdk import PortHandler, PacketHandler

BAUDRATE = 1_000_000
OVERLOAD_CLEAR_ADDR = 48   # register address to clear torque/overload flag
TORQUE_ENABLE_ADDR = 40

JOINT_NAMES = {
    1: "base rotation",
    2: "shoulder",
    3: "elbow",
    4: "wrist pitch",
    5: "wrist roll",
    6: "gripper",
}


def clear_motor(ph, port, motor_id: int, verbose: bool = True):
    # disable torque first, then re-enable — cleanest way to reset overload
    ph.write1ByteTxRx(port, motor_id, TORQUE_ENABLE_ADDR, 0)
    time.sleep(0.1)
    ph.write1ByteTxRx(port, motor_id, OVERLOAD_CLEAR_ADDR, 0)
    time.sleep(0.1)
    ph.write1ByteTxRx(port, motor_id, TORQUE_ENABLE_ADDR, 1)

    if verbose:
        label = JOINT_NAMES.get(motor_id, f"motor {motor_id}")
        print(f"  ✓  Cleared overload on ID {motor_id}  —  {label}")


def run(port_name: str, motor_id: int = None, clear_all: bool = False):
    port = PortHandler(port_name)
    ph = PacketHandler(0)

    if not port.openPort():
        print(f"[ERROR] Could not open port {port_name}")
        print("        Run: sudo chmod 666 /dev/ttyACM0")
        sys.exit(1)

    port.setBaudRate(BAUDRATE)
    print(f"\nConnected to {port_name}\n")

    if clear_all:
        print("Clearing overload on all 6 motors...\n")
        for i in range(1, 7):
            clear_motor(ph, port, i)
    else:
        target_id = motor_id if motor_id else 2  # default: shoulder
        clear_motor(ph, port, target_id)

    port.closePort()
    print("\n[OK]  Done. Move the arm to a compact neutral position before restarting teleoperation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear overload error on SO-101 motors.")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port (default: /dev/ttyACM0)")
    parser.add_argument("--id", type=int, default=None, help="Motor ID to clear (default: 2 = shoulder)")
    parser.add_argument("--all", action="store_true", help="Clear overload on all 6 motors")
    args = parser.parse_args()
    run(args.port, args.id, args.all)
