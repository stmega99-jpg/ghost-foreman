---
name: foreman-protocol
description: Protocol for consulting Ghost Foreman when an agent encounters an ambiguous requirement, design trade-off, or cross-agent conflict.
---

# Ghost Foreman Consultation Protocol

When working in a session managed by or connected to **Ghost Foreman**:
1. Before stopping to ask the human a design or specification question, call `foreman_get_policies` or send your question via `foreman_ask` with:
   - `project_id`: Current project identifier
   - `question`: The specific question or confirmation needed
   - `options`: Concrete options being considered (if any)
   - `impact`: Files affected and trade-offs
2. Distinguish between tool permission requests (handled by Kiro Crew's native approval system) and specification/design questions (handled by Ghost Foreman).
3. Respect locked specifications (`locked: true` in Policy Store). If a change to a locked specification is needed, explicitly mark `proposes_spec_change: true` so Ghost Foreman holds it for human confirmation.
