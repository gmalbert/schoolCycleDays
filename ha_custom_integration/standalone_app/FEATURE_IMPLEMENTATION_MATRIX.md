# School Cycle Days v0.4 — 20-Feature Implementation Matrix

This document maps the twenty product features requested after the app became Home-Assistant-independent to concrete code, routes, storage, and validation.

## 1. Automatic snow-day shift — IMPLEMENTED

- `ScheduleService.add_snow_day_and_shift()` stores the closure and rebuilds the authoritative profile schedule.
- Because cycle advancement happens only on eligible school days, the next school day automatically receives the skipped cycle position.
- UI: **Snow / emergency closure** on `/profile/<id>`.
- Test: `test_snow_day_shifts_cycle`.

## 2. Dry-run / preview mode — IMPLEMENTED

- `ScheduleService.preview()` generates a complete candidate schedule without writing `profile_schedule`.
- `GET /api/v1/profiles/<profile>/preview` returns summary, validation warnings, and candidate rows.
- The profile page links directly to the dry-run output.

## 3. Interactive calendar editing — IMPLEMENTED

- Profile schedule cells are clickable.
- Clicking a date loads that date into the date-override editor and scrolls the user to it.
- Override POST route applies the change and rebuilds the schedule.
- The original root calendar remains available as the polished month-style standalone view.

## 4. Per-date cycle overrides — IMPLEMENTED

- `schedule_overrides` table supports `school` and `no_school` overrides, optional cycle position, title, and note.
- Overrides are applied before weekday/closure logic.
- Forced school days can explicitly reset continuation to the selected cycle position.
- Remove route: `POST /profile/<profile>/override/remove`.
- Test: `test_date_override_can_force_cycle`.

## 5. Recurring closure rules — IMPLEMENTED

- `closure_rules` stores weekday, optional range, month, and nth-occurrence constraints.
- `ScheduleService._rule_dates()` expands those rules during every preview/rebuild.
- UI supports rules such as every Friday or the nth weekday of a month.
- Delete route: `POST /closure-rules/<id>/delete`.
- Test: `test_recurring_closure_rule`.

## 6. Multiple calendars / children — IMPLEMENTED

- `calendar_profiles` is the top-level ownership table.
- `cycle_definitions`, profile closures, holidays, overrides, schedule rows, sources, publications, snapshots and notifications are profile scoped.
- `/household` can create another school/child profile.
- `/profile/<id>` manages a profile independently.
- Test: `test_multiple_profiles_are_independent`.

## 7. Shared household view — IMPLEMENTED

- `/household` aggregates Today and Next School Day across every profile.
- The page also contains the profile-creation form.

## 8. Public read-only calendar link — IMPLEMENTED

- Every profile gets an unguessable `public_share_token`.
- `/share/<token>` renders a read-only schedule without management controls.
- `POST /profile/<profile>/tokens/rotate-share` invalidates the old URL.

## 9. Private ICS subscription URLs — IMPLEMENTED

- Every profile gets a separate unguessable `ics_token`.
- `/calendar/<slug>.ics?token=<token>` serves the authoritative profile feed.
- `POST /profile/<profile>/tokens/rotate-ics` invalidates the old subscription URL.
- Tokens are distinct from read-only browser share tokens.

## 10. Google Calendar / Outlook push — IMPLEMENTED

- `publisher_routes.py` contains functional Google Calendar API and Microsoft Graph execution paths.
- User supplies the external calendar ID and an OAuth access token; token acquisition is intentionally kept outside the schedule core.
- The publisher writes all-day events and persists returned external event IDs.
- For a public SaaS-style release, the next UX step is a first-class OAuth authorization wizard so users never paste tokens manually.

## 11. Calendar sync instead of regenerate-all — IMPLEMENTED

- `PublicationSyncPlanner` computes content hashes for locally authoritative rows.
- `published_events` records provider, local date, external event ID and last published hash.
- Plan partitions rows into create/update/delete/unchanged.
- Google and Outlook execution routes POST only creates, PATCH only changes, DELETE only removals.
- `POST /profile/<profile>/publish/plan` exposes the dry-run diff.
- Test: `test_sync_planner_detects_create_update_delete`.

## 12. District calendar URL subscription — IMPLEMENTED

- `external_sources` stores ICS URL sources and last hash/check time.
- `ICSUrlSource` downloads and parses external ICS feeds.
- Background `subscription_refresh_loop()` refreshes enabled feeds at `SCD_SOURCE_REFRESH_SECONDS` (default six hours).
- Manual refresh remains available from the profile page.

## 13. Smart ICS matching rules — IMPLEMENTED

- URL sources have configurable include/exclude term lists.
- Defaults include `No School`, `School Closed`, `Vacation`, and `Teacher Workday`.
- Both summary and description are searched case-insensitively.
- The original upload cleaner deliberately retains the historical stricter `SUMMARY starts with No School` behavior for compatibility.

## 14. Import review screen — IMPLEMENTED

- `POST /profile/<profile>/ics/review` parses an uploaded file but does not modify the database.
- Candidate dates are kept in the signed server session.
- `ics_review.html` presents checked candidates for review.
- `POST /profile/<profile>/ics/confirm` imports only selected candidates, then rebuilds.

## 15. Conflict detection — IMPLEMENTED

- `ScheduleService.validate()` identifies schedule configuration failures and warnings, including overrides outside the school year and cycle-number overrides that no longer exist.
- `GET /api/v1/profiles/<profile>/validation` exposes validation independently.
- Preview includes warnings before an external publish.
- Test: `test_validation_warns_about_invalid_override`.

## 16. Change history / audit log — IMPLEMENTED

- `audit_log` records timestamp, profile, action and JSON payload.
- Core profile changes, rebuilds, imports, token changes, external sync and notification delivery are audited.
- The profile page shows recent actions.

## 17. Undo last change — IMPLEMENTED

- `snapshots` stores profile/cycle/non-school/override/schedule state before important mutations.
- A rolling maximum of 20 snapshots per profile is retained.
- `POST /profile/<profile>/undo` restores the latest snapshot and rebuilds.
- Test: `test_undo_restores_non_school_state`.

## 18. Authentication + household accounts — IMPLEMENTED BASELINE

- `users` table supports username, PBKDF2-SHA256 password hash and role.
- `/login` doubles as first-run administrator setup when no users exist.
- Signed session cookies are provided by `SessionMiddleware`.
- `SCD_REQUIRE_LOGIN=true` enables login enforcement for management/API routes while read-only share/ICS endpoints remain usable by token.
- Share/ICS URLs are deliberately capability-token based rather than session based.
- Password hashing test: `test_password_hashing`.
- Before internet-facing v1.0: add CSRF tokens, login throttling, account recovery, HTTPS-only cookie mode and optional OIDC/Google/Apple login.

## 19. Mobile-first / PWA mode — IMPLEMENTED BASELINE

- All current standalone pages use responsive CSS.
- `/manifest.webmanifest` supports installation as a standalone web app.
- `/service-worker.js` provides cached GET fallback for previously viewed pages.
- Profile UI is usable on phone-width screens.
- Before store-quality distribution: add icon assets, richer offline shell/update messaging and accessibility audit.

## 20. Notifications — IMPLEMENTED

- `notification_targets` supports webhook and ntfy targets today and is adapter-extensible.
- Profile UI can configure and test targets.
- `notification_loop()` checks hourly.
- Each target gets at most one daily “tomorrow” notification because deliveries are persisted in `notification_deliveries`.
- Payload includes tomorrow and next-school-day information.

---

# Cross-cutting improvements included with these features

## Arbitrary cycle length

The scheduling engine no longer assumes five days. A profile can use A/B, three-day, six-day or other ordered rotations. Five entries remain the migration default only.

## Profile-scoped export / backup

`GET /api/v1/profiles/<profile>/export` returns a versioned JSON export containing profile settings, cycle definitions, closures, holidays, overrides, rules and schedule.

## Source/publisher architecture

`adapters.py` defines reusable boundaries for:

- `CalendarSource`
- `CalendarPublisher`
- `NotificationPublisher`

Implementations currently include ICS URLs, Google Calendar, Outlook/Microsoft Graph, generic remote JSON/webhook, webhook notifications, ntfy, MQTT Discovery, the standalone ICS feed and the optional legacy Home Assistant adapter.

## Pinned authoritative model

No external provider owns the school schedule. The data flow is:

```text
profile settings + cycle definitions + closures + holidays + rules + overrides
                                  |
                                  v
                         ScheduleService
                                  |
                                  v
                         profile_schedule
                                  |
             +--------------------+--------------------+
             |                    |                    |
        standalone UI        ICS / REST          optional adapters
                                                  MQTT / HA /
                                             Google / Outlook
```

This is the model that should be retained when the project is moved into its own repository.

# Runtime validation

The repository contains unit tests for the original engine, ICS cleanup, standalone schedule, and new product features. This development environment has previously been unable to resolve GitHub for an isolated clone, so do not treat commits alone as proof that the entire suite has run. Before merging/moving the repository run:

```bash
cd ha_custom_integration/standalone_app
python -m compileall school_cycle_days tests
pytest -q
```

Then run the end-to-end test plan in `../STANDALONE_TESTING_GUIDE.md`.
