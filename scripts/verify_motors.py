"""
verify_motors.py
----------------
Scans the servo bus and confirms all 6 motors are detected and responding.

Run this after every USB attach to confirm the arm is ready before doing
anything else. Saved us from blind-debugging calibration issues that were
actually just a loose cable.

Usage:
    python scripts/verify_motors.py
    python scripts/verify_motors.py --port /dev/ttyACM1   # for leader arm

Ports:
    follower arm  ->  /dev/ttyACM0
    leader arm    ->  /dev/ttyACM1
"""

import argparse
import sys
from scservo_sdk import PortHandler, PacketHandler

BAUDRATE = 1_000_000
EXPECTED_IDS = [1, 2, 3, 4, 5, 6]

# SO-101 joint map — so you know what's moving when something's missing
JOINT_NAMES = {
    1: "base rotation",
    2: "shoulder        ← most likely to overload, handle with care",
    3: "elbow",
    4: "wrist pitch",
    5: "wrist roll",
    6: "gripper",
}

def verify(port_name: str):
    port = PortHandler(port_name)
    ph = PacketHandler(0)

    if not port.openPort():
        print(f"[ERROR] Could not open port {port_name}")
        print("        Did you run: sudo chmod 666 /dev/ttyACM0 ?")
        print("        Did you run: usbipd attach --wsl --busid <id> ?")
        sys.exit(1)

    port.setBaudRate(BAUDRATE)
    print(f"\nScanning {port_name} at {BAUDRATE} baud...\n")

    found = []
    missing = []

    for motor_id in range(1, 20):  # scan wider range to catch mis-flashed IDs
        model, result, error = ph.ping(port, motor_id)
        if result == 0:
            found.append(motor_id)
            label = JOINT_NAMES.get(motor_id, "unexpected ID — check flashing")
            print(f"  ✓  ID {motor_id}  —  {label}")

    port.closePort()

    print()

    expected_set = set(EXPECTED_IDS)
    found_set = set(found)

    missing = sorted(expected_set - found_set)
    unexpected = sorted(found_set - expected_set)

    if missing:
        print(f"[WARN]  Missing IDs: {missing}")
        print("        Possible causes:")
        print("        - Cable not seated properly between motors")
        print("        - Motor not flashed with correct ID")
        print("        - Insufficient power (check DC adapter on waveshare board)")
    
    if unexpected:
        print(f"[WARN]  Unexpected IDs found: {unexpected}")
        print("        Motors were probably flashed with wrong IDs — reflash them.")

    if not missing and not unexpected:
        print(f"[OK]    All {len(EXPECTED_IDS)} motors detected. Arm is ready.")
    
    return len(missing) == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify all SO-101 motors are responding on the bus.")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port (default: /dev/ttyACM0)")
    args = parser.parse_args()
    verify(args.port)
