"""
reboot_motors.py
----------------
Sends a full reboot command to all motors on the bus.

This is different from clear_overload.py.

clear_overload  →  clears the overload protection flag, re-enables torque.
                   Motor stays powered, state is preserved.
                   Use when: overload error mid-session, arm still in position.

reboot_motors   →  full hardware reboot of the motor firmware.
                   Motor restarts from scratch, loses current state.
                   Use when: motor is behaving strangely after a bad session,
                   clear_overload didn't fix it, or the motor seems stuck in
                   an unknown state.

When to use this over clear_overload:
    - After a very long overload that may have corrupted motor state
    - Motor is responding to ping but not to position commands
    - Teleop is lagging or jittery on one joint after a bad session
    - Before a fresh calibration run — clean slate on all motors

Usage:
    python scripts/reboot_motors.py                     # reboot all 6
    python scripts/reboot_motors.py --id 2              # reboot one motor
    python scripts/reboot_motors.py --port /dev/ttyACM1 # leader arm

After rebooting:
    - Wait 3–5 seconds before sending any commands
    - Run verify_motors.py to confirm all motors came back up
    - If doing calibration after reboot, run set_neutral.py first
"""

import argparse
import sys
import time
from scservo_sdk import PortHandler, PacketHandler

BAUDRATE     = 1_000_000
REBOOT_ADDR  = 64    # STS3215 reboot register

JOINT_NAMES = {
    1: "base rotation",
    2: "shoulder",
    3: "elbow",
    4: "wrist pitch",
    5: "wrist roll",
    6: "gripper",
}


def reboot_motor(ph, port, motor_id: int):
    label = JOINT_NAMES.get(motor_id, f"motor {motor_id}")
    ph.write1ByteTxRx(port, motor_id, REBOOT_ADDR, 1)
    print(f"  ↻  Rebooting ID {motor_id}  —  {label}")
    time.sleep(0.3)


def run(port_name: str, motor_id: int = None):
    port = PortHandler(port_name)
    ph   = PacketHandler(0)

    if not port.openPort():
        print(f"[ERROR] Could not open port {port_name}")
        print("        Run: sudo chmod 666 /dev/ttyACM0")
        sys.exit(1)

    port.setBaudRate(BAUDRATE)
    print(f"\nConnected to {port_name}\n")

    if motor_id:
        reboot_motor(ph, port, motor_id)
    else:
        print("Rebooting all 6 motors...\n")
        for i in range(1, 7):
            reboot_motor(ph, port, i)

    port.closePort()

    print(f"\nWaiting 4 seconds for motors to come back up...")
    time.sleep(4)
    print("[OK]  Reboot complete.")
    print("\nNext steps:")
    print("  1. Run verify_motors.py to confirm all motors are responding")
    print("  2. Run set_neutral.py to move arm to safe position")
    print("  3. Then proceed with calibration or teleoperation\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full reboot of SO-101 motors.")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port (default: /dev/ttyACM0)")
    parser.add_argument("--id", type=int, default=None, help="Reboot a single motor by ID (default: all)")
    args = parser.parse_args()
    run(args.port, args.id)
