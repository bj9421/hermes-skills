---
name: design-philosophy-pattern
description: "PATTERN: Multi-phase/gated skills MUST include a 'Design Philosophy' section explaining why the structure exists. Covers problem table, phase mapping, inspiration differentiation, and guiding principle."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [skill-authoring, documentation, design-pattern]
    related_skills: [ha-powers, hermes-agent-skill-authoring]
---

# Design Philosophy Documentation Pattern

> **Rule:** Every multi-phase/gated skill MUST include a "Design Philosophy" section explaining *why* the structure exists, not just *what* it does.

## When to Apply

Any skill that defines a pipeline, workflow, phased process, or gated sequence:
- ha-powers (7-phase development pipeline)
- brainstorming + writing-plans (pre-coding gate)
- Any future pipeline/orchestrator skill

## Required Structure

Title: `## 🧠 Design Philosophy — Why This Exists` (or equivalent)

Must cover four elements:

### 1. The Problem Being Solved
Table format: "Failure Mode | What Happens | How This Fixes It"

### 2. Why This Specific Structure
Table: "Phase | Solves | Gate Output"

### 3. What This Skill Adds on Top of Its Inspiration
Explicitly separate original contribution from your additions.

### 4. The Guiding Principle
One sentence capturing the spirit of the skill.

## Placement in SKILL.md

After: Overview, Pipeline Diagram, Phase Gates
Before: Detailed Phase Descriptions, Progress Tracker

## Why This Matters

Future agents need to understand the *why* before they can judge when to bend the rules. Without the "why," phases look like arbitrary bureaucracy. With it, they're insurance against expensive mistakes.
