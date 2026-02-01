# Learned Patterns
Last updated: 2026-01-30 (Run #1)

## Safe Patterns (Don't Flag)
- Collapsed feedback forms until user clicks "Useful" or "Not useful" - Reduces visual clutter
- Minimal header design (single line with menu button) - Intentional for screen space
- Topic tags without scores - Simple presentation for non-technical users
- Gray timestamp text on article metadata - Intentional de-emphasis

## Risky Patterns (Always Flag)
- Test/debug articles visible on customer pages (e.g., "TechCrunch Test Article X")
- Missing summaries on customer-facing items - Looks broken to users
- Emoji-only navigation labels - Accessibility and professionalism concerns
- Inconsistent feedback UI states across items on same page - User confusion

## Uncertain (Watching)
- No numeric relevance scores shown - May be intentional simplification OR missing feature
- Feedback suggestion tone variation - Needs consistency guidelines
- Single-color design (minimal styling) - May be intentional minimalism OR incomplete design

## Statistics
- Total runs: 1
- Issues found: 11 (8 standard + 3 low-risk improvements)
- Critical issues: 1 (test articles visible to customers)
- False positive rate: N/A (first run)
