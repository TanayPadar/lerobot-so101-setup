"""
motor_status.py
---------------
Reads temperature, voltage, and current load from each motor and prints
a live status report.

This script would have saved serious debugging time during the shoulder
overload issue. Instead of waiting for a motor to fail mid-teleop, you
can see it running hot BEFORE it trips the protection.

Run this:
    - Before a long teleop or recording session — baseline check
    - After a session where a motor felt warm — check if it overheated
    - When a motor is behaving sluggishly — check if load is spiking
    - Anytime you suspect hardware stress

What the values mean:
    Temperature  —  in Celsius. STS3215 safe range: 0–70°C.
                    Above 60°C: slow down or pause.
                    Above 70°C: stop immediately, let it cool.

    Voltage      —  in Volts. Normal range: 6.0–8.4V (2S LiPo / DC adapter).
                    Below 5.5V: insufficient power, motors will behave erratically.
                    Above 8.5V: overvoltage, check your power supply.

    Load         —  0–1000 raw units. Represents torque load on the motor.
                    0–200:   normal
                    200–500: moderate load, monitor
                    500+:    high load, risk of overload soon
                    Near 1000: about to trip overload protection

Usage:
    python scripts/motor_status.py                      # single snapshot
    python scripts/motor_status.py --live               # refresh every 2s (Ctrl+C to stop)
    python scripts/motor_status.py --port /dev/ttyACM1  # leader arm
    python scripts/motor_status.py --live --interval 1  # refresh every 1s
"""

import argparse
import sys
import time
import os
from scservo_sdk import PortHandler, PacketHandler

BAUDRATE = 1_000_000

# STS3215 register addresses
ADDR_TEMPERATURE = 56
ADDR_VOLTAGE     = 62
ADDR_LOAD        = 60

JOINT_NAMES = {
    1: "base rotation",
    2: "shoulder",
    3: "elbow",
    4: "wrist pitch",
    5: "wrist roll",
    6: "gripper",
}

TEMP_WARN  = 60
TEMP_CRIT  = 70
LOAD_WARN  = 400
LOAD_CRIT  = 700
VOLT_LOW   = 5.5
VOLT_HIGH  = 8.5


def read_motor_status(ph, port, motor_id: int):
    temp,    r1, _ = ph.read1ByteTxRx(port, motor_id, ADDR_TEMPERATURE)
    voltage, r2, _ = ph.read1ByteTxRx(port, motor_id, ADDR_VOLTAGE)
    load,    r3, _ = ph.read2ByteTxRx(port, motor_id, ADDR_LOAD)

    if r1 != 0 or r2 != 0 or r3 != 0:
        return None

    voltage_v = voltage / 10.0

    return {
        "id":        motor_id,
        "name":      JOINT_NAMES.get(motor_id, f"motor {motor_id}"),
        "temp":      temp,
        "voltage":   voltage_v,
        "load":      load,
    }


def status_line(s: dict) -> str:
    # temperature indicator
    if s["temp"] >= TEMP_CRIT:
        temp_flag = "🔴 CRITICAL"
    elif s["temp"] >= TEMP_WARN:
        temp_flag = "🟡 WARM"
    else:
        temp_flag = "🟢 ok"

    # load indicator
    if s["load"] >= LOAD_CRIT:
        load_flag = "🔴 HIGH"
    elif s["load"] >= LOAD_WARN:
        load_flag = "🟡 MOD"
    else:
        load_flag = "🟢 ok"

    # voltage indicator
    if s["voltage"] < VOLT_LOW or s["voltage"] > VOLT_HIGH:
        volt_flag = "🔴 CHECK"
    else:
        volt_flag = "🟢 ok"

    return (
        f"  ID {s['id']}  {s['name']:<18} "
        f"Temp: {s['temp']:>3}°C {temp_flag:<14}  "
        f"Voltage: {s['voltage']:.1f}V {volt_flag:<12}  "
        f"Load: {s['load']:>4} {load_flag}"
    )


def print_status(port_name: str, ph, port):
    print(f"\n{'━' * 90}")
    print(f"  LeRobot SO-101 — Motor Status    {port_name}    {time.strftime('%H:%M:%S')}")
    print(f"{'━' * 90}\n")

    any_warn = False
    for motor_id in range(1, 7):
        s = read_motor_status(ph, port, motor_id)
        if s is None:
            print(f"  ID {motor_id}  {JOINT_NAMES.get(motor_id, ''):<18} [NOT RESPONDING]")
            any_warn = True
        else:
            line = status_line(s)
            print(line)
            if "🔴" in line or "🟡" in line:
                any_warn = True

    print(f"\n{'━' * 90}")

    if any_warn:
        print("\n  ⚠️  One or more motors need attention. Check flags above.")
        print("     High temp  → pause session, let cool before continuing")
        print("     High load  → motor is straining, check arm position or calibration")
        print("     Voltage ✗  → check DC power adapter connection on Waveshare board")
    else:
        print("\n  ✓  All motors nominal.")

    print()


def run(port_name: str, live: bool = False, interval: int = 2):
    port = PortHandler(port_name)
    ph   = PacketHandler(0)

    if not port.openPort():
        print(f"[ERROR] Could not open port {port_name}")
        print("        Run: sudo chmod 666 /dev/ttyACM0")
        sys.exit(1)

    port.setBaudRate(BAUDRATE)

    try:
        if live:
            print(f"Live mode — refreshing every {interval}s. Press Ctrl+C to stop.\n")
            while True:
                os.system("clear")
                print_status(port_name, ph, port)
                time.sleep(interval)
        else:
            print_status(port_name, ph, port)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        port.closePort()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read temperature, voltage, and load from SO-101 motors.")
    parser.add_argument("--port",     default="/dev/ttyACM0", help="Serial port (default: /dev/ttyACM0)")
    parser.add_argument("--live",     action="store_true",    help="Refresh continuously until Ctrl+C")
    parser.add_argument("--interval", type=int, default=2,    help="Refresh interval in seconds for live mode (default: 2)")
    args = parser.parse_args()
    run(args.port, args.live, args.interval)
