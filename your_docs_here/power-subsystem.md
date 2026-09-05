---
title: Power Subsystem
category: subsystems/power
updated: '2026-08-31'
related:
- thermal-subsystem.md
- overview.md
- telemetry-and-anomaly-detection.pdf
key_concepts:
- battery
- solar_panel
- power_budget
- thermal_dissipation
---

# Power Subsystem

The power subsystem is responsible for generating, storing, conditioning, and distributing electrical energy to every other subsystem on a CubeSat. It is usually the first subsystem sized during mission design, because nearly every other capability — payload duty cycle, downlink frequency, propulsion firing time — is ultimately constrained by how much power is available.

## Solar Panels

Body-mounted solar panels are the simplest option, covering the CubeSat's exterior faces, but deployable panels that unfold after launch can multiply the available collection area several times over. Panel sizing depends on orbit type: a sun-synchronous low Earth orbit gives fairly predictable illumination, while other orbits may include long eclipse periods that the battery has to cover entirely. Efficiency losses from panel pointing error, temperature, and degradation over mission life are all built into the power budget with margin.

## Battery Chemistry

The battery stores energy generated during sunlit periods for use during eclipse and peak-load events. Chemistry choice trades energy density, cycle life, and tolerance to the CubeSat's operating temperature range.

| Chemistry | Energy Density (Wh/kg) | Cycle Life | Typical Use |
|---|---|---|---|
| Li-ion | 150–250 | 500–1,000 cycles | Most common choice; high energy density for mass-constrained buses |
| LiFePO4 | 90–160 | 2,000–3,000+ cycles | Longer-duration missions where cycle life matters more than mass |
| NiMH | 60–120 | 500–1,000 cycles | Legacy or low-cost designs; more tolerant of overcharge |

## Power Budgeting

A power budget tracks generation against consumption across a full orbit, accounting for eclipse duration, panel pointing, and the duty cycle of every load. Margin is typically held in reserve for degradation over the mission lifetime and for unplanned high-power events like propulsion firings or payload bursts. When the budget is tight, operators reduce duty cycle on non-critical loads rather than risk a battery depth-of-discharge that shortens cycle life.

![Power distribution block diagram showing solar panels, battery, power conditioning unit, and regulated bus feeding each subsystem](power-distribution-block-diagram.png)

## Interaction with Thermal Dissipation

Batteries are not perfectly efficient: charging and discharging both generate waste heat, and this thermal dissipation has to be managed by the thermal subsystem, particularly during high-current events like eclipse recovery charging. Battery performance is itself temperature-dependent — capacity fades at low temperatures and cycle life degrades at high ones — so the power and thermal subsystems are tightly coupled by necessity rather than convenience. Power system telemetry, including bus voltage, battery temperature, and charge/discharge current, is one of the most frequently monitored parameter sets in anomaly detection, since a drifting battery trend is often the earliest sign of a developing spacecraft problem.
