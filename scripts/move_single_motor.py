"""
move_single_motor.py
--------------------
Move any single motor by ID to a target position, or run the full arm demo
sequence (all 6 motors one by one).

This was the first script that made the arm actually move. Built it during
setup to verify each motor before full calibration. Also used to shoot the
first video of the arm moving — each joint sweeping left/right/center.

Positions are in raw servo units (0–4095). Center is always 2048.
STS3215 motors: 0 = one extreme, 4095 = other extreme, 2048 = center.

Usage:
    # Move one motor to a specific position
    python scripts/move_single_motor.py --id 1 --pos 2048

    # Sweep one motor left → right → center (good for testing range)
    python scripts/move_single_motor.py --id 2 --sweep

    # Run full demo — all 6 motors sweep one by one (what we used for the video)
    python scripts/move_single_motor.py --demo

    # Change port for leader arm
    python scripts/move_single_motor.py --demo --port /dev/ttyACM1

Joint reference:
    ID 1  —  base rotation
    ID 2  —  shoulder        ← don't sweep too far, overload risk
    ID 3  —  elbow
    ID 4  —  wrist pitch
    ID 5  —  wrist roll
    ID 6  —  gripper

Safe sweep ranges (learned from calibration):
    ID 1:  1500 – 2500
    ID 2:  1700 – 2400   ← keep conservative, shoulder overloads when extended
    ID 3:  1700 – 2400
    ID 4:  1700 – 2400
    ID 5:  1700 – 2400
    ID 6:  1800 – 2300   (gripper open/close)
"""

import argparse
import sys
import time
from scservo_sdk import PortHandler, PacketHandler

BAUDRATE = 1_000_000
GOAL_POS_ADDR = 42       # register address for goal position on STS3215
CENTER = 2048

JOINT_NAMES = {
    1: "base rotation",
    2: "shoulder",
    3: "elbow",
    4: "wrist pitch",
    5: "wrist roll",
    6: "gripper",
}

SAFE_RANGES = {
    1: (1500, 2500),
    2: (1700, 2400),
    3: (1700, 2400),
    4: (1700, 2400),
    5: (1700, 2400),
    6: (1800, 2300),
}


def move(ph, port, motor_id: int, position: int, delay: float = 1.2):
    lo, hi = SAFE_RANGES.get(motor_id, (0, 4095))
    if not (lo <= position <= hi):
        print(f"[WARN]  Position {position} is outside safe range [{lo}, {hi}] for motor ID {motor_id}")
        print("        Clamping to safe range.")
        position = max(lo, min(hi, position))

    ph.write2ByteTxRx(port, motor_id, GOAL_POS_ADDR, position)
    time.sleep(delay)


def sweep(ph, port, motor_id: int):
    lo, hi = SAFE_RANGES.get(motor_id, (1700, 2400))
    label = JOINT_NAMES.get(motor_id, f"motor {motor_id}")
    print(f"  Sweeping ID {motor_id}  —  {label}")
    move(ph, port, motor_id, lo)
    move(ph, port, motor_id, hi)
    move(ph, port, motor_id, CENTER)


def demo(ph, port):
    print("\nCentering all motors first...\n")
    for i in range(1, 7):
        ph.write2ByteTxRx(port, i, GOAL_POS_ADDR, CENTER)
        time.sleep(0.3)
    time.sleep(1.5)

    print("Running full arm demo...\n")
    for motor_id in range(1, 7):
        sweep(ph, port, motor_id)
        time.sleep(0.5)

    print("\nAll done. Arm back at center.")


def run(port_name: str, motor_id: int = None, position: int = None,
        do_sweep: bool = False, do_demo: bool = False):

    port = PortHandler(port_name)
    ph = PacketHandler(0)

    if not port.openPort():
        print(f"[ERROR] Could not open port {port_name}")
        print("        Run: sudo chmod 666 /dev/ttyACM0")
        sys.exit(1)

    port.setBaudRate(BAUDRATE)
    print(f"\nConnected to {port_name}\n")

    if do_demo:
        demo(ph, port)

    elif do_sweep:
        if motor_id is None:
            print("[ERROR] --sweep requires --id")
            sys.exit(1)
        sweep(ph, port, motor_id)

    elif motor_id is not None and position is not None:
        label = JOINT_NAMES.get(motor_id, f"motor {motor_id}")
        print(f"Moving ID {motor_id} ({label}) to position {position}...")
        move(ph, port, motor_id, position)
        print("Done.")

    else:
        print("[ERROR] Provide --id + --pos, or --id + --sweep, or --demo")
        sys.exit(1)

    port.closePort()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Move SO-101 motors manually for debugging or demo.")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port (default: /dev/ttyACM0)")
    parser.add_argument("--id", type=int, help="Motor ID (1–6)")
    parser.add_argument("--pos", type=int, help="Target position in servo units (0–4095, center=2048)")
    parser.add_argument("--sweep", action="store_true", help="Sweep motor left → right → center")
    parser.add_argument("--demo", action="store_true", help="Run full arm demo — all 6 motors")
    args = parser.parse_args()
    run(args.port, args.id, args.pos, args.sweep, args.demo)
