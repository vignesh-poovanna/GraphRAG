---
title: 'Mission Case Study: Example CubeSat'
category: ops/mission-case-study
updated: '2026-08-31'
related:
- overview.md
- adcs-attitude-control.md
- telemetry-and-anomaly-detection.pdf
- power-subsystem.md
key_concepts:
- reaction_wheel
- anomaly_detection
- thermal_dissipation
- power_budget
- telemetry
---

# Mission Case Study: Example CubeSat

This case study follows a fictional 3U CubeSat, referred to here as EX-1, through its mission life to illustrate how the subsystems described elsewhere in this set actually interact in practice.

## Launch and Commissioning

EX-1 launched as a rideshare payload and was deployed into a sun-synchronous low Earth orbit. Within the first orbit, its deployable solar panels released and its UHF antenna deployed, giving ground operators their first telemetry contact a few hours after separation. Commissioning followed the standard sequence: an ADCS detumble to bring the tumbling spacecraft under control, followed by calibration of the reaction wheels, magnetorquers, and star tracker, and a checkout of the power, thermal, and communications subsystems before the payload was activated.

## Nominal Operations

For the first year of operations, EX-1 ran a routine cycle: fine-pointing at its payload targets during data-collection windows, returning to a sun-pointing mode between them to maximize power generation, and downlinking accumulated telemetry and payload data during ground station passes. The power budget held comfortably through this period, with battery state of charge recovering fully during each sunlit arc, and thermal dissipation from the battery and reaction wheels stayed within its expected baseline range.

## The Anomaly

About fourteen months into the mission, ground operators reviewing downlinked telemetry noticed a small but persistent upward drift in one reaction wheel's operating temperature and current draw for a given commanded speed — a signature consistent with early bearing wear. This is exactly the kind of trend that anomaly detection is designed to catch: no single telemetry point looked alarming on its own, but the moving average across successive passes showed a clear, steady climb that stood out against the wheel's established baseline.

Operators cross-checked the affected wheel's telemetry against the spacecraft's overall thermal trend and confirmed that the extra heat was localized to that one wheel rather than a broader thermal issue, which pointed toward a mechanical rather than an environmental cause. As a precaution, the flight team reduced that wheel's maximum commanded speed and shifted more of the fine-pointing workload onto the two healthier wheels and the magnetorquers, trading a small amount of pointing precision for a meaningful reduction in the degrading wheel's heat output and mechanical stress.

## Workaround and Recovery

The reduced-speed workaround stabilized the wheel's temperature trend within a few weeks, and the power budget absorbed the change easily since magnetorquer operation draws relatively little power compared to a reaction wheel running at full authority. Thermal margins across the spacecraft remained healthy throughout, since the affected wheel's heat output, while elevated relative to its own baseline, was never large enough on its own to threaten a subsystem-wide thermal limit. The case became a standing example, cited internally on the operations team, of how early anomaly detection on a single telemetry parameter — caught well before it became a functional failure — allowed a graceful workaround instead of a wheel loss.

## End of Mission

EX-1 continued science operations for the remainder of its planned lifetime under the adjusted wheel configuration. At end of life, the spacecraft was passivated — batteries discharged to a safe state and propulsion systems (where present) safed — and left to decay from orbit via atmospheric drag, consistent with standard end-of-life disposal practice for missions in its orbit regime.
