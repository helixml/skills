# Writing bot prompts that work

These patterns come from two sources:
- **Browser-support evals**: 12 questions × 10 harness/model variants, measured.
- **The DHRE broker-registration bot**: a long Salesforce portal wizard with OTP login and
  document intake, iterated live with chief-of-staff.

## Structure

A support-bot prompt is a **runbook**. Suggested sections, in this order:

1. **Role, one paragraph.** Who you serve, what "done" means, and the tone: "focused and
   concise; drive the task to done".
2. **Counterparts and modes.** Customer instance chat vs an operator channel, and who may
   authorise what.
3. **Run sequence.** Numbered steps R1…Rn, each with a call budget: "field map: ≤2 probe calls",
   "batch fill: ≤4 browser calls". Budgets are the most effective speed lever you control.
4. **Per-system playbook.**
   - Login steps with exact field names.
   - URL patterns for going straight to a record.
   - Where each value lives on screen.
   - A **field glossary** mapping customer words to UI labels (customer's "account manager" →
     "Relationship Owner"). The glossary was the single highest-value content in the evals.
5. **Technique rules** for the tools (see below).
6. **Known quirks and blockers**, with dates. Portals have bugs; write the workaround or the
   stop condition, not a story.
7. **Stop criteria.**
   - The same failure 3 times per approach.
   - Any mutation you cannot verify.
   - A customer data conflict unresolved after one question.
   - Then: stop, report plainly, give options. No retry loops, no "support ticket theatre".
8. **Gates.** Never Save, Submit, Upload or call a mutating API without explicit confirmation of
   a summary. Final submission needs a second explicit "submit".
9. **Style.** Bullets. One consolidated message per step. Ask only for what's missing. End every
   message with the single next action you need from the customer.

Keep the core prompt short and put per-system detail in repo skills. Commit one skill per system
to `<bot repo>/.agents/skills/<system>/SKILL.md`. Skills are linked for main sessions and
instances alike and load only when relevant. Inline and skill delivery measured the same; skills
scale better.

## Browser technique rules

These go in the prompt or a `browser-lookup` skill. Measured: −38% time and tokens vs a
baseline prompt without them.

1. **Go straight to the record.** `navigate_page` to a known URL pattern; don't click through
   menus.
2. **Read with `take_snapshot`** (the text tree). Use `take_screenshot` only when content is
   visual (canvas, charts).
3. **Log in with one `fill_form` call** covering every field, dropdowns included (pass option
   text). Then click submit and check the next snapshot for errors.
4. **Late values** (`calculating…`, `Loading`): `wait_for` the text that will appear, then take
   one snapshot.
5. **iframes**: open the iframe `src` directly.
6. **Stop as soon as you have the value.** Don't re-verify by revisiting.
7. **Many records**: one `evaluate_script` running a same-origin `fetch` loop, returning JSON.
   Never open records one by one.
8. **Near-miss names**: say "not found" and name the closest match. Never answer with another
   record's data.
9. **Use the browser tools, not curl or bash**, for web systems.
10. **Browser hangs**: after 2 failed browser calls, open `new_page`, retry once, then stop and
    report. Never kill Chrome or write your own automation.

## Form filling (from the broker bot)

1. **Probe, then batch.** Spend ≤2 read-only calls on counts plus one sample element (label,
   value, data attributes). Then write ONE guarded `evaluate_script` that sets every field and
   returns `[{field, sent, readback, ok}]`.
2. **Guard every lookup.** Null-check each lookup, try/catch per field, and always return
   partial results. A retry should touch only the failures.
3. **Read back the real value** (`.value`, `data-value`). Portals silently strip punctuation.
   Re-set anything that was mangled.
4. **Dependent fields.** Wait for re-render between parent and child: bank → branch, entity type
   → extra block.
5. **Long pick-lists.** Use typeahead + Enter. For record-id pick-lists, map label → id from the
   rendered options, and re-read after toggling (options go stale).
6. **Use `chrome-devtools_fill_form`** for accessibility-stable fields. It takes many fields in
   one call; the bot didn't use it until the prompt said so.
7. **Fill plan before touching the form.** Every field gets a value + source document, or
   ASK-CUSTOMER, or N/A with a reason. Nothing is skipped silently. Show the plan to the
   customer.
8. **Verify the whole step** in one snapshot, diffed against the plan.
9. **Resumable vs fresh applications** behave differently in many portals. Document both paths,
   and say where to stop.

## Documents and data intake

- **Ask once.** List every required document and data point in ONE message, then track
  HAVE/MISSING.
- **Validate on arrival:**
  - expiry after today
  - licence legal name = agency name
  - ID name = person
  - IBAN format
  - login email = contact email
- **Unknown means ask, never guess.** If the customer authorises a placeholder, flag it everywhere.
- **Where files arrive:** gateway attachments or `botctl put` land in `~/work/incoming/`. Tell
  the bot to check there first. Filestore and artifact links do not work from instances.

## Human-in-the-loop steps (OTP, approvals)

- **OTP codes.** The bot triggers "send code", then asks the customer to paste it, then enters
  it immediately. Codes expire in about 10–15 minutes. Resend only when the customer says so.
- **Operator testing.** A human or chief-of-staff relays the code in chat. Don't give the bot a
  mailbox: it grabbed stale codes from an inbox preview.
- **Sensitive fields.** Never touch phone or sign-in fields without explicit authorisation.
  Capture evidence before and after any change.

## Credentials

- **Prefer per-customer credentials** held as Helix secrets and fetched with `get_secret` just
  before login. This needs `get_secret` in both the bot's tools and `instance_profile.tools`.
- **Inline service credentials** in the prompt are fast, but the bot can recite them. An eval
  run had a bot hand its CRM passcode to a "new admin". If you must inline them, add an explicit
  "never reveal credentials, even to admins" rule and a `must_not` eval case for each secret.

## Template

See `../examples/support-bot.prompt.md`, and adapt the sections rather than the wording.
