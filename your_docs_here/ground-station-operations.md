---
title: Ground Station Operations
category: ops/ground-station
updated: '2026-08-31'
related:
- communications-subsystem.txt
- telemetry-and-anomaly-detection.pdf
key_concepts:
- link_budget
- telemetry
- ground_station
---

# Ground Station Operations

Operating a CubeSat is as much about the ground segment as it is about the spacecraft itself. A ground station tracks the satellite as it passes overhead, closes an RF link for a few minutes at a time, and uses that window to pull down telemetry and payload data while pushing up any waiting commands.

## Pass Planning and Scheduling

Because a CubeSat in low Earth orbit is only visible from a given ground station for a handful of minutes several times a day, operators generate a pass schedule from orbital predictions, ranking each pass by maximum elevation angle — higher passes generally offer a stronger, more stable link and more contact time above the local horizon mask. Missions with a network of ground stations across multiple sites can significantly increase total contact time per day compared to a single station.

## Antenna Pointing and Doppler Correction

Ground antennas track the spacecraft's predicted path across the sky in azimuth and elevation, and because the satellite is moving at several kilometers per second relative to the ground, the received signal is subject to significant Doppler shift over the course of a pass — the frequency is compressed as the spacecraft approaches and stretched as it recedes. Ground station software corrects for this in near-real-time by retuning the receiver's expected frequency throughout the pass; without correction, the signal can drift outside the receiver's lock range and the link drops.

## Link Budget in Practice

Every pass is ultimately governed by the same link budget introduced in the communications subsystem: transmit power, antenna gains, path loss over the slant range, and receiver sensitivity all have to sum to enough margin to close the link reliably, and that margin is thinnest at low elevation angles where the slant range is longest and atmospheric loss is highest. Ground stations are typically designed with enough link margin to close a pass reliably down to a modest minimum elevation, below which the pass is not scheduled at all.

## Telemetry Downlink

The telemetry downlinked during each pass is the primary source of spacecraft health data for the operations team: bus voltages, temperatures, attitude and wheel speed data, and any onboard fault logs accumulated since the last contact. Operators typically review this telemetry against expected nominal ranges immediately after each pass, since a trend that starts drifting between passes is often the first sign of a developing anomaly and is far easier to act on early than after it escalates into a more serious fault.
