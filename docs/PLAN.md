# monkey stable release plan

0.7.1.dev2 adds a public, hash-pinned source system-font preparation and static generation adapter around the existing CoreText resolver, Unity binding preparation, bundled Swift generator, and strict SDF input validator. GREA remains the only actual caller for the Foodstreet batch. The adapter declares source OS identity and visual equivalence unverified, leaves all source inputs immutable, and uses fresh output directories. See SOURCE-SYSTEM-FONTS.md. Dev1 fixed source0da189a remains unchanged in its private execution snapshot.

2026-11-04 isolated 0.7.1.dev1 Cocos maintenance candidate: explicit Toggle-binding presence and source-component gating prevent Unity JsonUtility's materialized null Spec from enabling an absent feature. Actual source Toggle rows still require the full strict spec during creation and saved readback. GREA alone owns real Foodstreet conversion/native-import; source and export checks do not claim native acceptance. Binary work is paused by user. Public stable 0.7.0 remains immutable; no publication or global upgrade is authorized.

The v0.7.0 line consolidates the fixed 0.7.0.dev9 source implementation. Distribution, isolated installation and the public CLI are validated before publication. Source/target support and remaining unknown behavior are documented in SUPPORT-MATRIX.md and RELEASE-v0.7.0.md. The 0.8 Unity-source development line remains independent.

Publication requires exact source commit and artifact checksums, declared dependencies and license files, relevant focused checks and combined-provider validation. Candidate preparation or installation alone does not mean a release is published; remote tag/commit and downloaded bytes must be checked separately.
