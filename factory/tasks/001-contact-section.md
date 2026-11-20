# 001 – Contact section

## Goal
A visible "Contact" section on the page, placed after `#join` and before the footer, with the Village's contact details.

## Scope
`index.html`, `styles.css`

## Acceptance criteria
- [ ] New `<section id="contact">` between `#join` and `<footer>`, with an `<h2>`, matching the heading/container markup of neighbouring sections
- [ ] Contains: email (`mailto:` link), phone (`tel:` link), location "Brighouse", and opening/drop-in hours — values taken from the CONTACT DETAILS block below, never invented
- [ ] Styled with existing CSS variables/classes where possible; any new CSS goes in `styles.css` only (no inline styles)
- [ ] Readable at 375px width (no horizontal scroll) and links/targets are at least 44px tall
- [ ] `scripts/validate.sh` passes

## CONTACT DETAILS (to be confirmed by user)
- Email: TBC
- Phone: TBC
- Hours: TBC
(If TBC, worker uses obvious placeholders `hello@example.org`, `01484 000000` and flags them in its report.)

## Docs impact
none: static page content only; the README already describes the site's files and contains no contact details.

## Runbook impact
none: no new way to run or operate the site; the contact section is plain HTML (placeholder values are flagged in the task Log for the user to replace).

## Status
validated
## Log
round 1: worker added #contact + .contact-link (placeholders: hello@example.org, 01484 000000, hours 'to be confirmed') → validator PASS (375px no overflow, links 44px)
