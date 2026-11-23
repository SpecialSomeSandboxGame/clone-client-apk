# UX notes

This document records the research, the audit of the first Repack tab, the
redesign, and the evidence used to verify it.

## Research

The redesign is based on established usability guidance, not on personal taste:

- Nielsen Norman Group, 10 usability heuristics:
  https://www.nngroup.com/articles/ten-usability-heuristics/
- Nielsen Norman Group, progress indicators:
  https://www.nngroup.com/articles/progress-indicators/
- Nielsen Norman Group, progressive disclosure:
  https://www.nngroup.com/articles/progressive-disclosure/
- Nielsen Norman Group, form design:
  https://www.nngroup.com/articles/web-form-design/
- GOV.UK Design System, error messages:
  https://design-system.service.gov.uk/components/error-message/
- GOV.UK Design System, check answers:
  https://design-system.service.gov.uk/patterns/check-answers/
- Qt documentation, wizard and layout guidance:
  https://doc.qt.io/qt-6/qwizard.html

The rules applied to this screen:

1. Visibility of status. The user must always know what the app is doing and
   what happens next.
2. One primary action. Competing primary buttons create hesitation.
3. Progressive disclosure. Show only what the current step needs. Advanced
   settings stay collapsed.
4. Error prevention before validation. Disable the action until the input is
   valid, and explain the blocker near the action.
5. User control. A long operation must be cancellable, and cancellation must
   leave a clear state.
6. Recognition over recall. Show the source, the new identity, and the effect
   of the rename together.
7. Actionable microcopy. Errors say what to do, not only what failed.
8. Keyboard access. File selection, run, and cancel must not require a mouse.

## Audit of the first Repack tab

The first tab was a single dense form followed by a raw diagnostics box, a log,
a progress bar, and the action buttons. The screenshots exposed these
problems:

- Two independent scroll areas sat side by side. The right column clipped its
  own content while the left had a separate scrollbar.
- The primary action was buried between two large text boxes.
- The diagnostics and log dominated the window before the user ran anything.
- The six-row "Ready check" repeated "Ready" and added noise when nothing was
  wrong.
- "Package summary" duplicated facts already shown in the source and identity
  cards.
- "What changes?" appeared in two places.
- The footer repeated the same status text as the progress card.
- There was no cancel, no inline validation, no shared state between
  inspection and the primary action, and no result state.
- The disabled primary button gave no local explanation.

## Redesign

### Layout

The Repack tab now has one page scroll and a fixed footer:

- Left column: the five input steps.
  - Source package: drop target, file picker, file size and split count.
  - App identity: current package, new application id, inline validation.
  - Appearance: optional launcher name, icon picker, 64 px preview, and clear
    action. Both fields are empty by default so the source name and icon stay.
  - Server endpoints: optional Server 1 and Server 2 replacement hosts, each
    exactly 18 characters, with inline errors.
  - Output and signing: output folder, keystore password (minimum 6 characters),
    release keystore, and an advanced alias field.
- Right column: context and outcome.
  - Package details: only data that is not already in the left column
    (version, SDK, ABIs, densities, languages, OBB) plus rename warnings.
  - Progress: hidden until a run starts. Seven named stages including the
    optional Appearance step, a state-colored bar, and the current stage.
  - Result: success, failure, or cancellation, with the error summary and
    the next action.
- Footer: one status line, the details toggle, cancel, and the primary action.

### State model

| State | Left column | Right column | Footer |
| --- | --- | --- | --- |
| Idle | Empty source, identity, signing | Package details placeholder | Disabled button, "Select an XAPK or APK." |
| Inspecting | Disabled while reading, refresh shows activity | Placeholder until info arrives | "Reading package information..." |
| Ready | Editable, inline validation | Compact summary and warnings | "Ready to repack." |
| Running | Disabled | Progress card with stages | "Repack in progress...", Cancel, "Repacking..." |
| Success | Editable | Green result with output path | "APK ready...", "Repack another" |
| Failed | Editable | Red result with the error summary | "Repack failed...", "Try again" |
| Canceled | Editable | Neutral result | "Repack canceled...", "Try again" |

### Details on demand

The raw package report and the full log sit in a details panel that is hidden
by default. The footer toggle opens it in any state, including after an
inspection failure. This keeps the default screen calm without hiding
diagnostics.

### Microcopy

- "Existing app data under the old package is not migrated; the new app uses
  a new data directory."
- "Letters, digits, and underscores only. Hyphens are invalid. The id must be exactly 20 characters."
- "Shown under the launcher icon. Leave empty to keep the current name."
- "App name cannot start with @ or ?"
- "PNG, JPG, or WebP. Minimum 48x48. Non-square images are center-cropped."
- "Server 1 endpoint must be exactly 18 characters."
- "Servers are replaced inside the native library; empty fields keep the current endpoints."
- "Key password must be at least 6 characters."
- "Used for this session only. Minimum 6 characters. Keep one keystore for all releases."
- Failure states name the failed stage and offer "Try again".
- Success states offer "Open folder", "Copy path", and "Repack another".

### Keyboard and focus

- `Ctrl+O` opens the source picker.
- `Ctrl+R` starts a repack when the form is valid.
- `Esc` cancels a running repack.
- The source field receives focus when the tab opens.
- The primary button carries a tooltip with its shortcut.

### Visual system

- Light and dark themes share the same spacing, card, and typography scale.
- Section titles, muted labels, field labels, and errors have distinct roles.
- Primary, secondary, ghost, and disabled states are visually distinct.
- Stage labels use Done, Running, Pending, Failed, and Canceled text plus
  color, so color is not the only signal.
- The progress bar changes color for success and failure.

## Evidence

The redesign was rendered through the real `MainWindow` with a live XAPK and
captured in these states:

- `docs/ux-idle.png`: empty state and disabled primary action.
- `docs/ux-ready.png`: inspected package, summary, warning, ready footer.
- `docs/ux-busy.png`: running stages, colored bar, cancel, disabled form.
- `docs/ux-failed.png`: failed stage, red bar, single retry action.
- `docs/ux-success.png`: green result, output actions, repack another.
- `docs/ux-validation.png`: inline package-length and password-length errors,
  with the primary action disabled.
- `docs/ux-appearance.png`: Appearance card with invalid app name and icon
  errors, plus the empty-state guidance.

Verification:

- `uv run pytest`: 76 passed, 1 skipped (the opt-in end-to-end test).
- The end-to-end repack test was rerun with an app name, icon, and both server
  endpoints and passed against the provided XAPK.
- `uv run ruff check src tests scripts build.py` and
  `uv run ruff format --check src tests scripts build.py`: clean.
- `uv run python scripts/check_style.py`: no em dash and no emoji.

## Follow-ups

These are intentionally out of scope for this pass:

- Cancellable package inspection. The inspector currently reports activity but
  does not accept a cancel request.
- Recent source files and a remembered last directory.
- System theme following instead of a manual selector.
- Accessible names and descriptive labels for a screen reader audit.
- A compact layout below 900 px wide. The current minimum is 640 px, where the
  page scroll keeps the two columns usable.
