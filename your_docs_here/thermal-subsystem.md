---
title: Thermal Subsystem
category: subsystems/thermal
updated: '2026-08-31'
related:
- power-subsystem.md
- adcs-attitude-control.md
- overview.md
key_concepts:
- thermal_dissipation
- battery
- reaction_wheel
- insulation
---

# Thermal Subsystem

In orbit, a CubeSat has no air around it to carry heat away by convection, so every watt of dissipated power has to leave the spacecraft by conduction to a radiating surface or by direct radiation to space. The thermal subsystem's job is to keep every component within its survival and operating limits despite that constraint, across both hot sunlit periods and cold eclipse periods.

## Passive vs. Active Thermal Control

Passive control uses material selection, surface coatings, and insulation to shape how heat flows and radiates without consuming power. Active control adds heaters, thermostats, and sometimes louvers or heat pipes to actively move heat where it's needed, at the cost of additional power draw and complexity. Most CubeSats lean heavily on passive design and reserve active heaters for a small number of temperature-sensitive components, such as batteries or oscillators.

## Insulation and Radiators

Multi-layer insulation (MLI) blankets — alternating layers of reflective film and low-conductivity spacer material — are the standard passive tool for isolating sensitive components from external temperature swings. Radiators, typically a dedicated external panel with a high-emissivity coating, are used to reject excess heat to space, often from the side of the spacecraft that avoids direct sun exposure.

| Material | Thermal Conductivity (W/m·K) | Typical Use |
|---|---|---|
| Aluminum 6061 | ~167 | Structural panels and heat spreaders |
| MLI blanket (layered) | ~0.0002 effective | External insulation against radiative heat loss/gain |
| Copper | ~400 | Heat straps and high-conductivity paths to radiators |
| Titanium | ~22 | Low-conductivity structural isolators and mounts |

![Thermal gradient diagram showing temperature distribution across the spacecraft body from sun-facing to shadow-facing sides](thermal-gradient-diagram.png)

## Internal Heat Sources

Two of the largest internal heat sources on a typical CubeSat are the battery and the reaction wheels. Battery charge and discharge cycles dissipate heat proportional to current squared, and this load spikes during eclipse-recovery charging or high-power payload operations. Reaction wheels generate friction heat continuously while spinning, and that heat output rises further as bearing wear increases over the mission lifetime — a wheel running hotter than its baseline is often an early indicator worth flagging. Because both sources are variable and load-dependent, thermal design has to budget for worst-case combinations rather than steady-state averages, and thermal telemetry is watched closely alongside power and ADCS telemetry as part of routine anomaly detection.
