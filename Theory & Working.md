# 🧠 How LeRobot Actually Works — Theory & Internals

This document explains what's happening under the hood when you run the SO-101 arm.

Not the commands. Not the setup steps. The actual mechanics — how motors know where they are, how two arms mirror each other, how a neural network learns from your demonstrations, and how it runs inference without ever looking at your dataset again.

Written from first principles after going deep into the codebase and architecture while building this system.

---

## Table of Contents

1. [How a Servo Motor Knows Where It Is](#1-how-a-servo-motor-knows-where-it-is)
2. [The Tick → Angle → Normalized Pipeline](#2-the-tick--angle--normalized-pipeline)
3. [How Teleoperation Actually Works](#3-how-teleoperation-actually-works)
4. [Why Calibration Is a Physical Process First](#4-why-calibration-is-a-physical-process-first)
5. [How Teleop Data Becomes Training Data](#5-how-teleop-data-becomes-training-data)
6. [The Problem With Naive Imitation Learning](#6-the-problem-with-naive-imitation-learning)
7. [ACT Policy Architecture](#7-act-policy-architecture)
8. [Action Chunking — The Core Idea](#8-action-chunking--the-core-idea)
9. [How the Camera Gets Processed](#9-how-the-camera-gets-processed)
10. [Training Loop](#10-training-loop)
11. [Inference — What Happens After Training](#11-inference--what-happens-after-training)
12. [Why Dataset Quality Matters More Than Quantity](#12-why-dataset-quality-matters-more-than-quantity)
13. [Distribution Shift and How to Fight It](#13-distribution-shift-and-how-to-fight-it)

---

## 1. How a Servo Motor Knows Where It Is

Every STS3215 servo motor in the SO-101 has a magnetic encoder built into the shaft. This encoder continuously measures the physical rotation of the motor and outputs a number called a **tick**.

The tick range for STS3215 motors is **0 to 4095** — that's 4096 discrete positions across a full 360° rotation.

```
0    = one extreme
2048 = center / neutral
4095 = other extreme
```

The encoder updates continuously as the motor moves. When you read a motor's position, you're reading its current tick value. When you write a position command, you're sending a target tick value and the motor's internal PID controller drives the shaft to that position.

This is the foundation of everything. Before any neural network, before any policy — the robot's entire sense of "where am I" comes down to these 12 numbers (6 motors × 2 arms), updated at ~30Hz.

---

## 2. The Tick → Angle → Normalized Pipeline

Raw ticks are hardware-specific and meaningless to a neural network. LeRobot converts them through a two-step pipeline before they touch any model.

### Step 1: Ticks → Degrees

```
angle_degrees = (tick - homing_offset) × (360 / 4096)
```

`homing_offset` is the value recorded during calibration — it represents what tick value corresponds to the physical zero position for that joint. This is why calibration matters: a wrong offset means every angle calculation is built on a wrong reference.

### Step 2: Degrees → Normalized (-1 to 1)

```
normalized = (angle_degrees - range_min) / (range_max - range_min) × 2 - 1
```

`range_min` and `range_max` are also recorded during calibration — they represent the physical limits of each joint's safe range of motion.

The normalized value sits between -1 and 1 regardless of which joint it is. This makes training stable — the model sees consistent value ranges across all joints instead of raw tick numbers that vary by motor and assembly.

### Why this matters in practice

This pipeline is why a loose motor horn broke calibration. The encoder was reporting a tick value that didn't correspond to the physical joint angle — because the horn was slipping instead of rotating with the shaft. The offset recorded during calibration was wrong. Every downstream calculation — angles, normalized values, training data — was built on that wrong foundation.

**Tighten every horn screw before calibration. The encoder measures shaft rotation. If the horn isn't locked to the shaft, you're measuring the wrong thing.**

---

## 3. How Teleoperation Actually Works

During teleoperation, LeRobot runs a tight real-time loop:

```
1. Read tick values from all 6 leader arm motors
2. Convert ticks → degrees → normalized (using leader calibration)
3. Send normalized values to follower arm
4. Follower converts normalized → degrees → ticks (using follower calibration)
5. Write tick targets to follower motors
6. Repeat at ~30Hz
```

The key insight: **leader and follower never communicate in raw ticks.** They communicate in normalized joint space. This means even if the two arms have slightly different physical assemblies (different horn seating positions, slightly different offsets), they still mirror each other correctly — because both sides go through their own calibration to reach a common normalized representation.

This is also why calibrating both arms independently matters. If you calibrate only one arm, or use the same calibration file for both, the normalized values don't map to the same physical positions on each arm.

---

## 4. Why Calibration Is a Physical Process First

Most people treat calibration as a software step — run the script, press Enter a few times, done.

It isn't. Calibration is a measurement process. The script is just recording what the human physically does with the arm.

When the calibration script asks you to move a joint to its limit and press Enter, it reads the tick at that exact moment and stores it as `range_max` or `range_min`. When it asks you to hold the neutral position, it reads the tick and calculates the `homing_offset`.

**If the arm drifted, slipped, or wasn't at the position you thought it was when you pressed Enter — that incorrect tick gets stored as a ground truth value.** Every subsequent session uses that bad reference.

### The three calibration rules we learned the hard way

**1. Clamp the arm.**
Without clamping, the arm shifts under its own weight when you release it to press Enter. Clamp it to the table so it holds position.

**2. Neutral position must carry the shoulder's weight.**
The shoulder motor (ID 2) holds the weight of the entire upper arm. If neutral is set to a fully extended position, the motor is fighting gravity from the moment it starts. It overloads. Set neutral to a compact, physically sustainable position — elbow bent, arm not outstretched.

**3. Check every horn screw first.**
A horn screw loose by even half a turn means the horn slips during the calibration movement. The motor shaft rotates but the joint doesn't move proportionally. The ticks recorded don't reflect the actual joint angles. You end up with offsets that look correct in the file but produce wrong physical positions when used.

---

## 5. How Teleop Data Becomes Training Data

When you record a dataset, LeRobot saves every timestep of every episode in a structured format:

```
dataset/
├── data/
│   └── chunk-000/
│       ├── episode_000000.parquet    ← joint positions + actions, every timestep
│       ├── episode_000001.parquet
│       └── ...
├── videos/
│   └── chunk-000/
│       ├── observation.images.cam_high_episode_000000.mp4
│       └── ...
└── meta/
    ├── stats.json                    ← mean + std of every value, for normalization
    ├── episodes.jsonl                ← episode metadata
    └── info.json                     ← dataset config
```

### What's in each parquet file

Each row in the parquet file is one timestep. Columns include:

- `observation.state` — normalized joint positions of the follower arm (6 values)
- `action` — normalized joint positions of the leader arm (6 values) — this is the supervision signal
- `timestamp` — time within episode
- `episode_index` — which episode
- `frame_index` — which frame within the episode
- `next.done` — whether this is the last frame

The video files contain the camera frames, indexed to match the parquet rows by timestamp.

`stats.json` stores the mean and standard deviation of every value across the entire dataset. These are used during training to normalize inputs and during inference to denormalize outputs back to real joint angles.

### Key point

The "actions" in the dataset are just the leader arm's joint positions at each timestep. The robot learned nothing from recording — it's just logged data. The learning happens during training, when a neural network tries to predict those actions from the observations.

---

## 6. The Problem With Naive Imitation Learning

The simplest form of imitation learning: train a model to predict `action_t` given `observation_t`. At inference, run the model at each timestep and execute the predicted action.

This is called **behavioral cloning** and it has a fundamental problem — **compounding errors**.

During training, the model always sees observations that came from expert demonstrations. Every input to the model was generated by the human doing the task correctly.

During inference, the model's own actions generate the next observations. The moment the model makes a small mistake — a joint position that's slightly off — the next observation is slightly different from anything in the training data. The model is now in unfamiliar territory. Its next prediction is less accurate. That error compounds with the previous one. By timestep 50 the arm is in a state it never encountered during training, and the policy starts producing meaningless outputs.

This is called **distribution shift** — the distribution of observations at inference time drifts away from the distribution seen during training.

Fixes exist (DAgger, data augmentation, more diverse demonstrations) but behavioral cloning at its core is fragile for this reason.

---

## 7. ACT Policy Architecture

ACT (Action Chunking with Transformers) addresses the compounding error problem with two key ideas: action chunking and a CVAE-based architecture that handles the multimodality of demonstrations.

The full architecture has two components:

### CVAE Encoder (training only)
- Takes the full action sequence for a window as input
- Compresses it into a small latent vector **Z**
- Z captures the "style" of the motion — fast vs slow, left approach vs right approach
- This handles the fact that there are multiple valid ways to complete the same task
- At inference time the CVAE encoder is discarded — Z is set to zero (prior mean)

### Transformer Decoder (training + inference)
- Takes: current joint positions + camera features + Z vector
- Outputs: next **100** joint position targets — one per timestep
- Standard transformer encoder-decoder architecture
- The 100 action queries are learned embeddings, similar to object queries in DETR

The transformer is the policy. The CVAE is a training stabilizer.

---

## 8. Action Chunking — The Core Idea

Instead of predicting action at timestep T, ACT predicts actions at timesteps T, T+1, T+2, ... T+99.

Execute all 100 actions. Then re-run the policy. Predict the next 100. Execute. Repeat.

At 30fps, 100 actions = ~3.3 seconds of planned motion per chunk.

### Why this fixes compounding errors

Within a chunk, errors don't compound — the model planned the full sequence together, with full knowledge of where it's going. Each action in the chunk is consistent with the others.

Between chunks, the policy re-observes the scene and re-plans. If drift has occurred, the next chunk is planned from the current (drifted) state — which partially corrects for it.

### Temporal ensembling

ACT actually runs the policy every timestep, not just at chunk boundaries. At each timestep it generates a new 100-action prediction. The executed action is a weighted average of all active predictions for that timestep — predictions from the current step plus predictions for this timestep from recent policy calls.

This produces smoother motion and makes the policy more robust to noise in individual predictions.

The weight decays exponentially for older predictions — recent policy calls have higher weight.

---

## 9. How the Camera Gets Processed

Camera frames go through a **ResNet-18 backbone** — a standard pretrained convolutional neural network originally trained on ImageNet for image classification.

In ACT, ResNet-18 is used as a feature extractor:

```
RGB frame (H × W × 3)
→ ResNet-18 conv layers
→ Feature map (spatial grid of feature vectors)
→ Flatten spatial dimensions
→ 49 feature vectors of dimension 512  (for a 7×7 feature map)
→ Linear projection → 49 tokens of transformer dimension
```

These 49 tokens are treated identically to how word tokens are treated in a language transformer. They get positional embeddings. They attend to each other and to the joint position tokens in the transformer.

So from the transformer's perspective: "here are 49 visual tokens describing what I see, and 6 joint tokens describing where my arm is — predict the next 100 positions."

The ResNet weights are either frozen (pretrained ImageNet weights, fast training) or fine-tuned end-to-end with the rest of ACT (slower training, potentially better performance). This is a hyperparameter in LeRobot's training config.

---

## 10. Training Loop

```
For each batch of timesteps sampled from the dataset:

  1. Sample a window of T timesteps from a random episode
  2. For each timestep in the window:
     a. Load joint positions (observation.state)
     b. Load camera frame → ResNet → 49 visual tokens
     c. Load the next 100 actions (supervision signal)

  3. CVAE encoder:
     - Takes the 100 future actions
     - Outputs latent Z (mean + log variance)
     - Sample Z using reparameterization trick

  4. Transformer decoder:
     - Input: visual tokens + joint tokens + Z
     - Output: 100 predicted joint positions

  5. Loss:
     - Reconstruction loss: MSE between predicted and actual 100 actions
     - KL divergence loss: keeps Z close to standard normal prior
     - Total loss = reconstruction + β × KL

  6. Backpropagate. Update weights.
```

The KL divergence term (weighted by β) is what makes this a CVAE rather than a plain autoencoder. It regularizes the latent space so that Z=0 (the prior) produces reasonable actions at inference time, when the CVAE encoder isn't available.

Training typically runs for 80,000–100,000 steps. On a GPU (T4 or better) this takes 2–4 hours. On CPU it takes 12–24 hours.

---

## 11. Inference — What Happens After Training

At inference time:

```
1. Observe current joint positions → normalize → joint tokens
2. Capture camera frame → ResNet → 49 visual tokens
3. Set Z = 0 (prior mean — CVAE encoder not used)
4. Run transformer decoder → 100 predicted joint positions
5. Execute the first action (or a temporally ensembled version)
6. Move to next timestep. Repeat.
```

**The dataset is not used at inference time.**

The robot doesn't compare live camera frames to stored frames. It doesn't look up what to do from a database of demonstrations. It runs the learned function — the transformer weights — forward on live inputs.

The demonstrations shaped the weights during training. After training, those weights encode the task. The data is gone. What remains is a function: observation → action.

This is the fundamental difference between a lookup system and a learned system. A lookup system needs the data at inference. A learned system has internalized it.

---

## 12. Why Dataset Quality Matters More Than Quantity

Because ACT learns a distribution over demonstrations.

If your 200 demonstrations show 5 different ways to approach the same grasp — left side, right side, fast, slow, different wrist angles — ACT learns a distribution that covers all of them. At inference, it samples from this distribution. The result is often hesitant, averaged-out motion that doesn't cleanly execute any of the approaches.

If your 50 demonstrations are consistent — same approach angle, same speed, same wrist orientation — ACT learns a tight, well-defined distribution. Inference is clean and decisive.

### What "consistent" means in practice

- Same starting position every episode
- Same object position every episode (or controlled variation)
- Same grasp strategy every episode
- Smooth, deliberate movements — no jerking or second-guessing
- Complete the task fully every episode — no half-attempts

### How many episodes

- 50 episodes: minimum for a simple pick-and-place in a fixed setup
- 100 episodes: more robust, handles minor position variation
- 200+ episodes: needed for harder tasks or more variation in the scene

For a first policy — aim for 50 clean, consistent episodes of the exact same task in the exact same setup. Prove the policy works. Then add variation.

---

## 13. Distribution Shift and How to Fight It

Even with good data, distribution shift will appear when you test the policy in slightly different conditions.

**Causes:**
- Different lighting than during recording
- Object slightly out of position
- Arm starting from a slightly different position
- Camera shifted between recording and inference

**Fixes:**

| Fix | When to use |
|---|---|
| More diverse demonstrations | If the shift is predictable (e.g. object position varies) |
| Data augmentation (random crop, color jitter) | For lighting and camera variation |
| DAgger — record correction demonstrations | When the policy almost works but fails at one specific point |
| Better visual encoder (e.g. fine-tuned ResNet or ViT) | For generalization across large visual variation |
| Tighter experimental control | Simplest fix — keep recording and inference conditions identical |

For a first policy on a fixed task — tight experimental control is the right approach. Remove variables. Prove the policy works cleanly. Then deliberately introduce variation and collect data to cover it.

---

## Summary

```
Motor encoder → ticks (0–4095)
    ↓ calibration (homing_offset, range_min, range_max)
Normalized joint positions (-1 to 1)
    ↓ teleoperation loop
Leader arm mirrors → follower arm

Dataset recording → parquet + video + stats.json
    ↓ training
ResNet encodes camera → 49 visual tokens
Joint positions → 6 joint tokens
CVAE encodes future actions → latent Z
Transformer: visual tokens + joint tokens + Z → 100 predicted actions
Loss: MSE(predicted, actual) + β × KL(Z, prior)

Inference:
Z = 0
Transformer: live visual tokens + live joint tokens → 100 actions
Execute. Re-observe. Re-predict.
Dataset not used. Weights are the policy.
```

---

*Written by [Tanay Padar](https://github.com/TanayPadar) while building the SO-101 setup in Pune, India.*
*Follow the build on X: [@TanayPadar](https://twitter.com/TanayPadar)*
