# Feedback Policy

- Detect negative feedback about age, pace, or type.
- Parse multiple negative signals from one user message when possible.
- Avoid recommending explicitly rejected titles again.
- Persist rejected preference signals into session memory so later turns do not restart from scratch.
- Reuse previously accepted soft preferences when building a refined intent.
- If the feedback is specific enough, refine and retry once.
- If feedback is too vague, ask one clarification question.
