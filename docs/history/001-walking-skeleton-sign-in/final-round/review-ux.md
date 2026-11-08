VERDICT: PASS

## Summary
- Reviewed arch-web sign-in, app shell, user menu and sign-out against the spec, from code and tests only (no dev server or browser run).
- States covered: "Signing in…", "Signing out…", sign-in unavailable with retry, 403 "no access" screen with Sign out, profile load error with Try again, missing-config screen.
- 401 and silent-renew errors send the user back through sign-in.
- Accessibility is sound: real buttons, aria-expanded/aria-controls on the menu, Escape closes it and restores focus, status/alert roles.
- Copy is short, plain English; viewport meta is present and the layout is simple enough for a phone.

## Findings
None.

## Notes
- arch-web:src/components/UserMenu.tsx: menu does not close on outside click (only Escape or toggle). Minor.
- arch-web:src/components/Shell.tsx: a very long name could crowd the header on a phone (px-6, no truncation). Minor.
