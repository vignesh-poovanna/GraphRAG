---
title: ADCS — Attitude Determination and Control
category: subsystems/adcs
updated: '2026-08-31'
related:
- thermal-subsystem.md
- telemetry-and-anomaly-detection.pdf
- mission-case-study-example-cubesat.md
key_concepts:
- reaction_wheel
- attitude_control
- gyroscope
- anomaly_detection
---

# ADCS — Attitude Determination and Control

The Attitude Determination and Control Subsystem (ADCS) is responsible for knowing which way the spacecraft is pointing and for changing that orientation on command. Attitude control matters for almost every other subsystem: solar panels need to face the sun, antennas need to face the ground station during a pass, and payload sensors need to point at their targets.

## Actuators and Sensors

Reaction wheels are the primary fine-pointing actuator on most three-axis-stabilized CubeSats: spinning a small flywheel faster or slower exchanges angular momentum with the spacecraft body to rotate it. Magnetorquers generate a magnetic dipole that reacts against Earth's magnetic field, useful for coarse control and for "desaturating" reaction wheels that have spun up to their momentum limit. Determination relies on a mix of sensors — gyroscopes for short-term rate sensing, sun sensors and magnetometers for coarse orientation, and star trackers for high-precision attitude knowledge.

| Sensor Type | Measurement | Typical Accuracy |
|---|---|---|
| Gyroscope | Angular rate | 0.01–1 deg/s bias drift |
| Sun sensor | Sun vector | 0.1–1 degree |
| Magnetometer | Local magnetic field vector | 0.5–3 degrees |
| Star tracker | Absolute attitude quaternion | 0.001–0.01 degree |

![Three-axis attitude control diagram showing reaction wheel orientation and body axes for pitch, roll, and yaw](attitude-control-3axis-diagram.png)

## Reaction Wheel Heat and Degradation

Reaction wheels are also one of the subsystem's closest links to the thermal subsystem: bearing friction generates continuous heat that rises as the wheel spins, and that heat output tends to climb further as bearing lubrication degrades over the mission lifetime. This makes wheel temperature and wheel speed two of the most useful telemetry parameters for anomaly detection on the ADCS side. A wheel that draws more current than expected for a given commanded speed, or that runs hotter than its established baseline, is a classic early signature of bearing wear — often visible in telemetry trends well before the wheel approaches an actual failure, which gives operators time to plan a workaround such as shifting attitude control authority to a healthy wheel or to the magnetorquers.

## Attitude Control Modes

Most missions define a small set of attitude control modes: a detumble mode right after deployment, a sun-pointing safe mode that maximizes power generation, and a fine-pointing operational mode for payload or communications tasks. Transitions between modes are usually automatic, triggered by onboard fault detection logic, so that the spacecraft can protect itself even during a period without ground contact.
