# Emergent Rules for the System of Systems

## Purpose

This note records the reasoning used to derive the emergent rules in the vessel drainage system-of-systems experiment. It separates engineering discovery from deterministic execution and explains how the approach can scale when constituent models are independently authored and versioned.

## Starting Point: Mission Flow

Rule discovery started from the end-to-end mission rather than from a cross-product of constituent requirements:

```text
collect water -> demand drainage -> pump water -> accept flow -> discharge water -> report status
```

At each handoff, the integrator asks:

1. What guarantee leaves the upstream constituent?
2. What assumption must the downstream constituent receive?
3. What failure becomes possible only after selecting both constituents?
4. What end-to-end or degraded-mode claim can no constituent prove alone?

This produces a small set of checks over connected interfaces. It avoids comparing every requirement in every project with every other requirement.

## Public Contract Facts

Each constituent keeps its internal architecture and local assurance evidence private. The composition consumes only a deliberately small export surface:

| Constituent | Public facts used by composition |
|---|---|
| Pumping unit `1.1.0` | `deliveredCapacity_m3h = 100`, `operationalUnitCount = 2`, `singlePumpCapacity_m3h = 60` |
| Piping network `2.2.0` | `supportedCapacity_m3h = 110`, `acceptedPumpCount = 2`, `flowPathAvailable = true` |
| Well monitoring `0.9.0` | `requiredDrainageCapacity_m3h = 90`, `outletAvailable = true`, `operatorFeedbackAvailable = true` |

The contract boundary follows assume-guarantee reasoning. If one constituent guarantees $G_A$ and a connected constituent assumes $A_B$, compatibility requires:

$$
G_A \Rightarrow A_B
$$

Local compliance is necessary but insufficient. Two locally valid systems can still be incompatible when composed.

## Derived Emergent Rules

### `SOS-001 CapacityCompatibility`

$$
pump.deliveredCapacity \ge well.requiredDrainageCapacity
$$

The well establishes demand while the pumping unit supplies capacity. A passing pump model alone cannot prove it is sized for the selected drained space. With the current baseline, $100 \ge 90$.

### `SOS-002 PipingCompatibility`

$$
pipe.supportedCapacity \ge pump.deliveredCapacity
$$

The pipe network must carry the output of the selected pumps. A valid network may still be undersized for a separately valid pumping unit. The baseline passes because $110 \ge 100$.

The negative case `SOS-002-NEG` selects a historical piping contract supporting only $80\,m^3/h$. It must fail against $100\,m^3/h$ pump output. This proves the boundary can reject an incompatible composition rather than merely produce green execution results.

### `SOS-003 ConnectionCompatibility`

$$
pipe.acceptedPumpCount \ge pump.operationalUnitCount
$$

Every operational pump requires an accepted piping connection. Independent checks do not establish interface cardinality. The current baseline compares two accepted connections with two operational units.

### `SOS-004 EndToEndFlowPath`

$$
well.outletAvailable \land pipe.flowPathAvailable
$$

Water needs a continuous route from collection point to discharge. Neither endpoint can establish continuity alone. This rule required semantic engineering judgment: someone had to recognize that well outlet availability and piping path availability jointly represent the mission-level flow path.

An LLM was not required to derive this rule. An engineer could identify it by tracing the mission flow and interfaces. An LLM can accelerate discovery by proposing likely semantic joins, but the model does not make the proposal authoritative.

### `SOS-005 DegradedOperation`

$$
pump.singlePumpCapacity \ge 50 \land well.operatorFeedbackAvailable
$$

After one unit is unavailable, useful remaining capacity and observable operating status must coexist. This combines physical resilience from the pumping subsystem with operational awareness from monitoring. Neither constituent can prove this degraded system behavior independently.

## Compatibility Matrix

The runtime MVP varies one public contract fact at a time while holding the locked baseline constant. Each mutation represents a plausible constituent revision and predicts which emergent rules should change.

Examples include undersized piping, excessive delivered pump flow, changed pump count, missing flow path, insufficient single-pump capacity, and missing operator feedback. The matrix demonstrates selective invalidation: a changed fact reruns the rules that depend on it rather than forcing arbitrary comparisons between unrelated local requirements.

This is also a falsifiability mechanism. Known incompatible mutations must produce `FAIL`, while compatible selections must remain `PASS`.

## Deterministic Assurance Pipeline

Discovery can involve interpretation; execution must not. The MVP makes a composition repeatable through:

- canonical JSON serialization;
- SHA-256 content digests for immutable constituent archives;
- exact project, commit, version, and digest entries in a composition lock;
- verification of archive contents before contract resolution;
- a baseline hash covering the selected composition;
- fixed-step synchronous mock data;
- deterministic replay ordering for asynchronous events;
- append-only JSONL observations and evidence;
- `INCONCLUSIVE` for stale runtime data instead of silently treating it as valid.

Runtime observations never overwrite SysML source values. They create new evidence tied to the locked baseline and scenario.

## Scaling

The method scales by graph connectivity, not by the total requirement cross-product. Let constituent contracts be nodes and their connected assumptions and guarantees be edges. Rules are evaluated on affected edges and on explicitly owned end-to-end claims.

When a constituent changes:

1. Verify its package digest and exact locked identity.
2. Determine which exported facts changed.
3. Find compatibility and emergent rules that consume those facts.
4. Re-evaluate only that dependency closure.
5. Preserve previous evidence and append the new baseline result.

This keeps private model detail out of the composition and limits invalidation to meaningful dependencies.

## LLM-Assisted Discovery

An LLM can help discover candidate emergent rules by reading mission text, interface descriptions, requirement prose, names, units, and topology. Useful tasks include:

- suggesting guarantee-to-assumption matches;
- finding unit or cardinality mismatches;
- proposing end-to-end paths and degraded scenarios;
- identifying missing semantic metadata;
- drafting candidate formulas and traceability explanations.

LLM output remains a proposal. An engineer must approve the meaning, threshold, applicability, and safety consequence. Approved rules become typed SysML constraints or deterministic evaluator expressions, covered by positive and negative cases. No LLM participates in the acceptance verdict at runtime.

## Toward More Automated Derivation

Future constituent contracts could reduce manual semantic matching by exposing:

- typed ports and explicit connectors;
- flow direction and transported item types;
- units, bounds, and multiplicity;
- formal assumptions and guarantees;
- mission-role tags such as source, transport, sink, and observer;
- state and failure-mode semantics;
- requirement and evidence traceability identifiers.

With those facts, tooling can generate many boundary obligations directly: producer output versus consumer capacity, connector multiplicity, unit compatibility, and graph reachability. Semantic claims such as `SOS-004` could then be suggested from an explicit connected flow path rather than inferred from attribute names. Human approval remains necessary for mission interpretation and acceptance policy, while package resolution and verdict execution stay deterministic.