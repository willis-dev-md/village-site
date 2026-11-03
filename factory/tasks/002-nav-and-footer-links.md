# 002 – Link Contact from nav and footer

## Goal
Visitors can reach the Contact section from the header nav and footer. Depends on 001.

## Scope
`index.html`, `styles.css` (only if needed)

## Acceptance criteria
- [ ] Header `<nav aria-label="Main">` has a "Contact" link to `#contact`, placed before the "Register interest" pill
- [ ] Footer has a link to `#contact`
- [ ] Nav still fits at 375px (no overflow/wrap breakage)
- [ ] No other nav links removed or reordered
- [ ] `scripts/validate.sh` passes (anchors resolve)

## Status
validated
## Log
round 1: worker added header + footer links → validator FAIL (footer link dark-on-dark, 20px tall)
round 2: worker added `footer a` colour/hover/44px rules in styles.css → validator PASS (14.7:1 contrast, hover 11.5:1, 44px, no overflow at 375px)
