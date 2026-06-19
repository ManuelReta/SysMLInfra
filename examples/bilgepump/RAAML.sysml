// =============================================================================
// BilgePump::RAAML
// Layer: Safety Metadata Library
// Purpose: Pure OMG RAAML v1.0 metadata def blocks.
// These stereotypes are applied as annotations (#MetadataName)
// to elements in Safety.sysml and FMEA.sysml.
// This package has NO imports — it is a standalone metadata library.
//
// Reference: OMG RAAML v1.0 (Risk Analysis and Assessment Modeling Language)
// https://www.omg.org/spec/RAAML/1.0
//
// COMPATIBILITY NOTE:
// metadata def and #Annotation syntax requires SysML v2 Pilot API JAR
// version ≥ 2022-06 release. Verify JAR version before committing:
// curl localhost:9000/ | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])"
// Fallback: replace each 'metadata def' with 'attribute def' and remove
// '#' annotation usages in Safety.sysml and FMEA.sysml (loses formal
// RAAML stereotype semantics but compiles on older JARs).
//
// Import chain: Nothing imports RAAML except Safety.sysml and FMEA.sysml.
// RAAML ← Safety (annotations on UCAs and Losses)
// RAAML ← FMEA   (annotations on failure modes and constraint defs)
// =============================================================================

package BilgePump_RAAML {
    private import ScalarValues::*;

    // =========================================================================
    // STPA / STAMP Constructs
    // =========================================================================

    // -------------------------------------------------------------------------
    // Hazard
    // A system-level condition that, combined with a worst-case environment,
    // will lead to a Loss. Corresponds to STAMP Hazard concept.
    // SOURCE: STPA Handbook (MIT Press, 2018) §3.2; OMG RAAML §7.3
    // -------------------------------------------------------------------------
    metadata def Hazard {
        attribute hazardId : String; // e.g. "H-1"
        attribute description : String; // Short hazard statement
        attribute lossRefs : String; // Comma-separated Loss IDs, e.g. "L-0,L-1"
        attribute severity : String; // "catastrophic" | "critical" | "marginal" | "negligible"
        attribute regulatoryRef : String; // e.g. "SOLAS II-1 Reg.35"
        attribute sourceDoc : String; // Source document ID
        attribute section : String; // Section within source document
    }

    // -------------------------------------------------------------------------
    // Loss
    // An outcome that is unacceptable to stakeholders: injury, loss of life,
    // environmental damage, mission failure, or financial loss.
    // SOURCE: STPA Handbook §3.1; OMG RAAML §7.2
    // -------------------------------------------------------------------------
    metadata def Loss {
        attribute lossId : String; // e.g. "L-0"
        attribute description : String;
        attribute category : String; // "safety" | "environmental" | "mission" | "financial"
        attribute severity : String; // "catastrophic" | "critical" | "marginal" | "negligible"
        attribute regulatoryRef : String;
        attribute sourceDoc : String;
        attribute section : String;
    }

    // -------------------------------------------------------------------------
    // UCA (Unsafe Control Action)
    // A control action issued by a controller that, in a particular context,
    // leads to a hazard. Defined by component, action, guideword, and context.
    // SOURCE: STPA Handbook §4.2; OMG RAAML §7.5; XSTAMPP UCA table format
    // -------------------------------------------------------------------------
    metadata def UCA {
        attribute ucaId : String; // e.g. "UCA-001"
        attribute controlAction : String; // e.g. "ActivatePumpA"
        attribute guideword : String; // STPA guideword: "Not Provided" | "Wrong Value Provided" | "Provided Too Late" | "Applied Too Long"
        attribute context : String; // Context in which the UCA is hazardous
        attribute hazardRefs : String; // Comma-separated Hazard IDs
        attribute severity : String;
        attribute failureModeLink : String; // Link to FMEA failure mode ID (optional)
        attribute transitionRef : String; // State machine transition name that eliminates this UCA (optional)
        // e.g. "MONITORING_to_PUMP_A_ACTIVE" — cross-ref to StateMachine.sysml
        attribute sourceDoc : String;
        attribute section : String;
    }

    // =========================================================================
    // FMEA Constructs
    // =========================================================================

    // -------------------------------------------------------------------------
    // FailureMode
    // A specific way in which a component can fail, with FMEA ratings.
    // Follows the AIAG FMEA 4th Edition / MIL-STD-1629A format.
    // SOURCE: MIL-STD-1629A; AIAG FMEA 4th Edition; OMG RAAML §8.2
    // -------------------------------------------------------------------------
    metadata def FailureMode {
        attribute fmId : String; // e.g. "FM-S-001"
        attribute component : String; // Component name
        attribute instance : String; // Part usage instance name
        attribute failureModeText : String; // Failure mode description
        attribute failureEffect : String; // System-level effect
        attribute severity : Integer; // 1–10 AIAG scale
        attribute occurrenceRating : Integer; // 1–10
        attribute detection : Integer; // 1–10
        attribute rpn : Integer; // Computed RPN = S×O×D
        attribute ucaRef : String; // Linked UCA if applicable
        attribute hazardRef : String;
        attribute stateRef : String; // State machine state associated with this failure mode (optional)
        // e.g. "FAULT" or "FAILOVER" — cross-ref to StateMachine.sysml
        attribute sourceDoc : String;
        attribute section : String;
    }

    // -------------------------------------------------------------------------
    // FaultTree
    // Top-level event and gate structure for a fault tree analysis (FTA).
    // Minimal representation compatible with OMG RAAML §9. Full fault trees
    // require a dedicated FTA tool; this metadata tags the top event on a
    // SysML constraint def that models the fault tree logic.
    // SOURCE: IEC 61025 — Fault tree analysis; OMG RAAML §9.3
    // -------------------------------------------------------------------------
    metadata def FaultTree {
        attribute ftId : String; // e.g. "FT-001"
        attribute topEvent : String; // Undesired top event (matches a Hazard description)
        attribute gate : String; // Root gate type: "OR" | "AND"
        attribute cutSets : String; // Comma-separated minimal cut sets (simplified)
        attribute sourceDoc : String;
        attribute section : String;
    }

    // -------------------------------------------------------------------------
    // SafetyRequirement
    // A derived safety requirement that was generated from a STPA UCA or
    // FMEA corrective action. Traceability bridge between safety analysis
    // results and formal requirement definitions in Requirements.sysml and
    // Safety.sysml.
    // SOURCE: STPA Handbook §5.1 (Safety Constraints → Safety Requirements)
    // -------------------------------------------------------------------------
    metadata def SafetyRequirement {
        attribute srId : String; // e.g. "SR-001"
        attribute derivedFrom : String; // UCA ID or FMEA failure mode ID that generated this requirement
        attribute rationale : String; // Why this requirement addresses the identified hazard
        attribute verificationMethod : String; // "analysis" | "test" | "inspection" | "demonstration"
        attribute sourceDoc : String;
        attribute section : String;
    }
} // package BilgePump_RAAML
