---
title: CubeSat Mission Overview
category: subsystems/overview
updated: '2026-08-31'
related:
- power-subsystem.md
- thermal-subsystem.md
- mission-case-study-example-cubesat.md
key_concepts:
- mission_phases
- subsystem_overview
---

# CubeSat Mission Overview

A CubeSat is a small satellite built from standardized cubic units, typically 10 cm on a side (1U), and launched in multiples of that unit (3U, 6U, 12U). The standard was originally developed to give university teams a low-cost, repeatable path to orbit, and it has since become common for commercial constellations, technology demonstrations, and government research payloads. What makes CubeSats tractable for small teams is that every mission, regardless of purpose, is built from the same handful of subsystems working together inside a very tight mass, power, and volume budget.

## Mission Phases

Every CubeSat mission moves through a similar sequence of phases from integration through disposal. The table below summarizes the major phases, their typical duration, and the subsystem activity that dominates each one.

| Mission Phase | Typical Duration | Key Subsystem Activity |
|---|---|---|
| Integration & Test | 2–6 months | Power, OBC, and comms bring-up; environmental testing |
| Launch & Early Orbit | Hours to 1 week | Deployment, solar panel and antenna release, first telemetry contact |
| Commissioning | 2–6 weeks | ADCS detumble and calibration, subsystem checkout |
| Nominal Operations | 6 months – 5+ years | Payload operations, routine telemetry and anomaly monitoring |
| End-of-Life & Deorbit | Weeks to years | Passivation, propulsion or drag-based deorbit, final telemetry |

## Subsystem Summaries

**Power** generates, stores, and distributes electrical energy using solar panels and onboard batteries, and it has to balance generation against every other subsystem's draw across each orbit.

**Thermal** keeps every component within its survival and operating temperature limits using a mix of passive insulation and active heaters or radiators, since a CubeSat has almost no atmosphere around it to carry heat away.

**Attitude Determination and Control (ADCS)** points the spacecraft using reaction wheels, magnetorquers, and sensors like gyroscopes and star trackers, which matters for pointing solar panels at the sun, antennas at the ground, and payloads at their targets.

**Communications** handles uplink commands and downlink data over RF links in bands like UHF, VHF, or S-band, and its performance is governed by the link budget between the spacecraft and the ground station.

**Onboard Computer (OBC)** runs the flight software that sequences every other subsystem, handles fault detection and watchdog resets, and manages onboard data storage.

**Propulsion**, when present, provides delta-v for orbit maintenance, collision avoidance, or deorbit; many CubeSats fly without propulsion and rely on atmospheric drag instead.

**Telemetry** is the continuous stream of housekeeping data — voltages, temperatures, wheel speeds, and more — that every other subsystem produces and that ground operators use for anomaly detection.

These subsystems are deeply interdependent: power budget constrains propulsion and payload duty cycles, thermal dissipation from batteries and reaction wheels drives thermal design, and telemetry and anomaly detection tie the whole spacecraft's health picture together. The documents in this set look at each subsystem individually before tying them back together in a mission case study.
