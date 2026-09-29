# SPEC — example

**Date:** 2026-09-29 · **Status:** draft · **Owner:** agent · **Approved:** yes

## OUT OF SCOPE
No new pages.

## MUST NOT BREAK
The checkout.

## RISKS
Cache may hide the change; purge it.

## DONE WHEN

- [x] C1 · The page renders without console errors at 1280 px.
      MEASURED BY: Playwright run, count console errors.
      EVIDENCE: playwright 14:02, 0 console errors, screenshot shots/1280.png

- [x] C2 · The contact form sends a mail to the shop.
      MEASURED BY: submit the form, fetch the inbox over IMAP.
      EVIDENCE: Submit the form, fetch the inbox over IMAP.
