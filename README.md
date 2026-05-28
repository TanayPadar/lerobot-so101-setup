# 🤖 LeRobot SO-101 Robotic Arms — Full Setup from Zero

Complete setup log for the Hugging Face **SO-101 robotic arm** on Windows 11 + WSL2.
This covers everything from environment install to both arms assembled, all 12 motors flashed, and teleoperation running.

A real build log — including the parts that broke.
Caution -: Order / Keep some extra parts if possible. 3D Printed parts can break easily sometimes. It may waste your days.

---

## 📦 What's in here

| Phase | Status |
|---|---|
| WSL2 + Ubuntu 24.04 environment | ✅ done |
| Python 3.12 + LeRobot 0.5.1 install | ✅ done |
| ROS2 Jazzy install | ✅ done |
| USB passthrough (usbipd-win) | ✅ done |
| Motor flashing — all 12 servos | ✅ done |
| Both arms assembled | ✅ done |
| Calibration | ✅ done |
| Teleoperation working | ✅ done |

---

## 🖥️ System

- **OS:** Windows 11 + WSL2 (Ubuntu 24.04)
- **LeRobot version:** 0.5.1
- **Python:** 3.12 (not 3.10 — see gotchas)
- **ROS2:** Jazzy
- **Hardware:** SO-101 follower + leader arms, STS3215 motors (C044 and C046 variants — both compatible)
- **USB adapter:** Waveshare Bus Servo Adapter board
- **Ports:** follower = `/dev/ttyACM0`, leader = `/dev/ttyACM1`

---

## ⚙️ Environment Setup

### 1. WSL2 + Python

LeRobot 0.5.1 needs **Python 3.12**, not 3.10. The official docs say 3.10 — ignore that for this version.

On Ubuntu 24.04, Python 3.12 is available via deadsnakes PPA:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-venv -y
```

Also install system deps:

```bash
sudo apt install -y git cmake build-essential ffmpeg libsm6 libxext6 libgl1
```

> ⚠️ On Ubuntu 24.04, `libgl1-mesa-glx` is renamed to `libgl1`. Don't use the old name.

### 2. Install uv

LeRobot recommends `uv` over pip. Install it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then add to PATH — the install script sometimes doesn't do this automatically:

```bash
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### 3. Clone and install LeRobot

```bash
cd ~
git clone https://github.com/huggingface/lerobot.git
cd lerobot
uv venv --python=python3.12 .venv
source .venv/bin/activate
uv pip install -e ".[feetech]"
```

> ⚠️ The `[feetech]` extra is mandatory — it installs the servo drivers for SO-101. Without it, nothing hardware-related will work.

Verify:

```bash
python -c "import lerobot; print(lerobot.__version__)"
```

### 4. ROS2 Jazzy

```bash
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu \
  $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update
sudo apt install ros-jazzy-desktop -y
```

Source it permanently:

```bash
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

Verify (ROS2 doesn't have `--version`, do this instead):

```bash
ros2 doctor
# should show: All 5 checks passed
```

---

## 🔌 USB Passthrough (Windows → WSL2)

This is the most common pain point. Every session you need to re-attach the USB device to WSL.

### Install usbipd on Windows

In PowerShell (admin):

```powershell
winget install --interactive --exact dorssel.usbipd-win
```

### Every session — attach USB to WSL

```powershell
# In PowerShell (admin):
usbipd list           # find the busid for your robot
usbipd attach --wsl --busid 1-5   # replace 1-5 with your actual busid
```

```bash
# In WSL:
sudo chmod 666 /dev/ttyACM0
ls /dev/ttyACM*       # confirm device is visible
```

> ⚠️ The busid can change between sessions (e.g. `3-3` → `1-5`). Always run `usbipd list` first.

> ⚠️ Device appears as `/dev/ttyACM0` not `/dev/ttyUSB0`. Don't get confused by old tutorials.

---

## 🔧 Motor Flashing

### Hardware wiring

```
Laptop (USB-C) → Waveshare Bus Servo Adapter board → white/black cable → Motor
```

**Critical:** The Waveshare board jumper must be in **position B (USB-SERVO)**. If it's in position A, motors won't be detected.

**Critical:** USB-C alone does **not** provide enough voltage for STS3215 motors. You must connect an external DC power adapter to the barrel jack on the board. Without it, the motors won't respond.

### Flashing with Feetech FD (Windows GUI)

The LeRobot terminal script for motor flashing can be unreliable on Windows. Use the **Feetech FD Windows GUI software** instead:

1. Download Feetech FD from the official Feetech site
2. Connect one motor at a time to the board
3. Set ID 1–6 for follower arm motors (label them F1–F6)
4. Set ID 1–6 for leader arm motors (label them L1–L6)
5. Flash one motor at a time — never connect multiple unflashed motors on the same bus

Verify all motors detected after flashing:

```bash
# In WSL with venv active:
python -c "
from scservo_sdk import PortHandler, PacketHandler
port = PortHandler('/dev/ttyACM0')
port.openPort()
port.setBaudRate(1000000)
ph = PacketHandler(0)
for i in range(1, 7):
    model, result, error = ph.read2ByteTxRx(port, i, 3)
    if result == 0:
        print(f'Motor ID {i}: detected ✓')
    else:
        print(f'Motor ID {i}: NOT found ✗')
port.closePort()
"
```

---

## 📐 Calibration

**Clamp the arm to a table before calibrating.** Without clamping, the arm drifts when you press Enter and calibration data is wrong.

```bash
# Follower arm:
python src/lerobot/scripts/lerobot_calibrate.py \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0

# Leader arm:
python src/lerobot/scripts/lerobot_calibrate.py \
  --teleop.type=so101_leader \
  --teleop.port=/dev/ttyACM1
```

The script asks you to move each joint to its range limits, then to neutral position. Take your time — bad calibration here causes overload errors later.

Calibration files saved to:
```
~/.cache/huggingface/lerobot/calibration/
```

### Fixing bad calibration manually

If the arm jumps to a wrong position on startup (e.g. elbow fully extended), the `homing_offset` in the calibration JSON is wrong. Edit it directly:

```bash
nano ~/.cache/huggingface/lerobot/calibration/robots/so_follower/None.json
```

Find the joint with the wrong offset and set it to `0`, then fine-tune with small increments until the neutral position looks correct.

---

## 🕹️ Teleoperation

```bash
python src/lerobot/scripts/lerobot_teleop.py \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --teleop.type=so101_leader \
  --teleop.port=/dev/ttyACM1
```

Move the leader arm. The follower mirrors it in real time.

### Known issue — motor ID 2 overload error

The shoulder motor (ID 2) throws an overload error when the arm is in a fully extended position. This is a physical load issue — the motor struggles against the arm's weight when fully outstretched.

Fix: keep the arm in a compact position during teleoperation. If the error fires mid-session, clear it with:

```bash
python -c "
from scservo_sdk import PortHandler, PacketHandler
port = PortHandler('/dev/ttyACM0')
port.openPort()
port.setBaudRate(1000000)
ph = PacketHandler(0)
ph.write1ByteTxRx(port, 2, 48, 0)
print('Overload cleared on motor ID 2')
port.closePort()
"
```

---

## ⚠️ Gotchas (the stuff no doc tells you)

| Problem | Fix |
|---|---|
| `libgl1-mesa-glx` not found | Use `libgl1` on Ubuntu 24.04 |
| LeRobot needs Python 3.10 | For v0.5.1, use Python 3.12 |
| `uv` not found after install | Manually add `~/.local/bin` to PATH |
| Motors not detected | Check jumper on waveshare board — must be position B |
| Motors not responding | External DC power required, USB-C power alone is insufficient |
| Device not found in WSL | Re-run `usbipd attach` every session, busid may change |
| Scripts not found at `lerobot/scripts/` | In v0.5.1 scripts moved to `src/lerobot/scripts/` |
| Arm jumps to wrong position on startup | Edit homing_offset in calibration JSON directly |
| `ros2 --version` errors | Normal — ROS2 doesn't support that flag. Use `ros2 doctor` |
| Calibration magnitude error | Arm was at an extreme when you pressed Enter — reclamp and retry from neutral |

---

## 📁 What's next

This repo ends here — hardware ready, teleoperation confirmed.

Next repos:
- [`lerobot-so101-teleoperation`](https://github.com/TanayPadar) — dataset recording with OV9281 camera
- [`lerobot-act-policy`](https://github.com/TanayPadar) — training runs and results

---

## 👤 About

Built by [Tanay Padar](https://github.com/TanayPadar) — 21, Pune, India.

Follow the build on X: [@TanayPadar](https://twitter.com/TanayPadar)
