# Raiker personal beta: human tester guide

**For:** people who have never used Raiker. **Platform:** Windows PC.
**Prepared:** 2026-11-10. **Status:** instructions, not completed test results.

Raiker is a personal AI assistant. You can ask it questions, dictate a draft,
and let it carry out actions you have permitted. An **approval** is a request
for your permission. A **model** is the AI service that writes its answers.

This guide covers the remaining checks that need a person's own perception,
physical equipment, account consent or acceptance decision. Automated tests
cannot establish whether *you* can hear, understand, trust and comfortably use
the product. You do not need to write code, open a terminal or repair anything.

Passing these checks does **not** mean the whole beta is ready. Engineering
defects and automated security checks remain the development team's job.

## 1. The coordinator prepares your test pack

The person who sent you this guide is your **coordinator**. They must fill in
this table before you begin. If an item needed for your assigned check is
missing, report **Blocked** and ask the coordinator to supply it.

| Item | Coordinator fills in |
|---|---|
| Private contact for questions and results | ____________________ |
| Test date and your tester identifier; a nickname is fine | ____________________ |
| Exact Raiker version/build and approved installer filename | ____________________ |
| Where to get that installer; integrity already checked by coordinator | ____________________ |
| Dedicated test PC or permission to use this PC | ____________________ |
| Start with a new test account, or the supplied test account | ____________________ |
| Model name already prepared for Chat; local or named online provider | ____________________ |
| Maximum model spending and time allowed | ____________________ |
| Assigned checks: H-01, H-02, H-03, H-04, H-05, H-06 | ____________________ |
| For H-02: NVDA installed, configured modifier key and Windows version | ____________________ |
| For H-03: physical microphone/headset and speech engines prepared | ____________________ |
| For H-04: service, account, allowed permissions and private test fixture | ____________________ |

Passwords, API keys and recovery keys are supplied separately if needed. Never
put them in this table, a screenshot or your report. You should not have to
register developer applications, configure OAuth, change a firewall or install
a sandbox. Those are coordinator/developer preparation tasks.

Use made-up test content. Do not connect a work or personal account unless
you own it, have permission and have agreed the exact scope with the coordinator.
Use a private test mailbox/calendar; do not send a message to anyone else.

## 2. How to record a result

For **each assigned check**, record one of these words:

| Result | Use it when |
|---|---|
| Pass | You completed every required step and observed the expected result. |
| Fail | You tried it and the product behaved incorrectly or was unusable. |
| Blocked | Missing equipment, an account, preparation or permission prevented a fair attempt. |
| Not tested | You did not attempt it. Give the reason. |

An error is useful evidence. Stop at the failed step, write down what happened
and contact the coordinator. Do not repeatedly retry an action that might send,
create or delete something. A coordinator's workaround does not turn the
original failure into a pass; record the help and any later retest separately.

To open **Settings**, select the cog at the top of Raiker. To find another
page, press **Ctrl+K**, type its name, use the arrow keys to choose the result
and press **Enter**. **Esc** closes a menu or dialog. If you cannot find a
named control, report that rather than guessing a different action.

## 3. H-01 — First-time understanding and informed choices

**Allow:** 15–20 minutes. **Needs:** a first-time user and the approved test
build. **Why a person:** a script cannot tell us whether an unfamiliar person
understands the wording and consequences without coaching.

1. Open the approved installer, or open the installed Raiker if the coordinator
   has already installed it. Write down which starting point you used.
2. If Windows shows a security, publisher or administrator prompt, record its
   words. This private build may be unsigned. Follow only the coordinator's
   instructions for the exact approved file; this guide is not permission to
   bypass an unfamiliar warning. If approval is unclear, stop as **Blocked**.
3. Follow the visible setup instructions. Use the test account provided, or
   create the new test account the coordinator assigned. Keep its password private.
4. Before asking for help, write one sentence describing what you think Raiker
   can do and what it still needs from you. Record any screen you do not understand.
5. Open **Chat**. Find the model name near the message box. In your own words,
   say whether you think your typed words stay on the PC or go to an online
   provider. Then compare your answer with the privacy line on screen.
6. Type `Suggest three names for a pretend houseplant. Do not use tools.`
   Send it and wait for the answer. Find the information beneath the answer
   that says which model answered and what the turn cost, if shown.
7. Open **Approvals**. If it is empty, check that “Nothing waiting on you” is
   visually centered in the page's content, and that you understand the message.
   If there is a decision, do not approve an unfamiliar action. Describe what
   you think approving it would do, and ask the coordinator to compare that
   description with the actual action.
8. Open the **?** help button. Try to find help for one thing that confused you.

**Pass when:** you can explain the selected model/privacy choice, understand
whether an approval performs an action, and find relevant help without hidden
instructions. Record confusing language even if you finished the task. A wrong
or missing answer is a failure of that observation, not something you must fix.

**Return:** your explanations, confusing words/screens, help received and
redacted screenshots of any unclear prompt. This is a comprehension check;
it does not qualify installer upgrades, sandbox enforcement or network privacy.

## 4. H-02 — Real screen-reader use with NVDA

**Allow:** 30–45 minutes. **Needs:** NVDA prepared by the coordinator, audible
speech and a person able to use it. If you are new to screen readers, ask for
orientation first and record that fact; do not guess whether speech is correct.
**Why a person:** automated label checks cannot judge the spoken experience,
reading order, useful announcements or whether focus is understandable.

1. Start **NVDA** from the Windows Start menu. Open Raiker. Confirm you hear
   the name of the focused control. Ask the coordinator to check your NVDA
   setup if you hear nothing; mark **Blocked** until it works.
2. Put the mouse aside. Use **Tab** to move forward and **Shift+Tab** to move
   backward. Listen for names, roles and states, such as button, selected or
   unavailable. Record any unexplained icon, repeated label or silent control.
3. Reach **Chat**, find the box named **Prompt**, and type
   `Reply with one short sentence about a pretend blue bicycle.` Send it.
   Listen while the answer arrives. Can you discover and read the final answer
   without continuous announcements making it impossible to follow?
4. Start another request: `Write a long story about a pretend blue bicycle.`
   Reach **Stop safely** using the keyboard and activate it once available.
   Can you tell from speech whether work stopped, is stopping or already finished?
   If the answer finishes before you reach Stop, record **Not tested** for this
   part; the coordinator can arrange a longer safe fixture for a separate retest.
5. Press **Ctrl+K**, search for **Approvals**, choose it with the arrow keys
   and press **Enter**. Can you identify Pending/History and the empty state
   or each actual decision? Do not approve a real action for this test.
6. Open a menu, then press **Esc**. Is focus returned to the control that
   opened it? Open **?** help, read part of it and close it. Can you return to work?
7. Use the keyboard to open **Settings → Backups**. Identify the backup action
   and any existing backup's state by speech. Making/restoring a backup is not
   required for this screen-reader check.
8. Describe any place you got stuck, needed the mouse, lost focus, heard too
   much speech or could not determine what happened.

**Pass when:** every attempted core step is usable by keyboard and speech,
with understandable names, order, focus and result announcements. A sighted
coordinator pointing at the screen is assistance to record, not proof of success.

**Return:** NVDA version, configured modifier key, step numbers, spoken words
or a short description of them, and the help you needed. A speech recording is
optional and must contain only consented test content. Never record passwords.

## 5. H-03 — Your real microphone, voice and hearing

**Allow:** 20–30 minutes. **Needs:** a physical microphone and speakers or
headphones. Use a comfortable volume. The coordinator must prepare managed
Whisper/Kokoro through **Settings → Voice**; the built-in Test alone and a
synthetic microphone do not count as this check.

**Why a person:** we have tested generated audio and browser capture, but
cannot establish accuracy for your accent, room, equipment or hearing.

1. Open **Settings → Voice**. Confirm Listening and Speaking are installed.
   If they are unavailable, ask the coordinator; mark **Blocked** rather than
   switching to an unrelated transcription service.
2. Select **Preview this voice**. Can you hear it clearly at a comfortable
   volume? Note distortion, gaps, speed or pronunciation that makes it hard to follow.
3. Open a new **Chat**. In the message box, type `Please keep this note.`
   Do **not** send it. Select **Dictate**, the microphone button. Allow microphone
   access only for this approved test if Windows or the app asks.
4. Say naturally: “Please remind me on Tuesday at three thirty to water the
   plants.” Select **Done dictating**. This is a draft, not an instruction to
   create a real reminder. Check that your typed note remains and the new words
   have the correct day, time and meaning. Punctuation may differ.
5. Confirm the text has **not** been sent automatically. Check that Raiker's
   listening indication ends and the operating system no longer indicates that
   Raiker is recording. Close other recording apps beforehand so their indicators
   do not confuse this observation. Do not send the draft.
6. Clear the draft. Dictate the same sentence once more in your ordinary room
   conditions. You may try normal background conversation or a fan only with
   everyone affected consenting. Record the conditions; do not create loud noise.
7. Type another short draft, start Dictate, speak a few words and select
   **Cancel dictation**. Your original typed draft should remain, nothing
   should be submitted and recording should end.
8. If using a removable USB headset, start Dictate and unplug **that headset
   only**. Do not unplug storage or other equipment. Check that Raiker explains
   the interruption, preserves your typed draft and ends recording. Reconnect
   it and try dictation again. If unsuitable for your equipment, mark this part
   **Not tested** and say why.
9. With the prepared Chat model, send `Reply exactly: The pretend garden has
   three blue flowers.` Use the answer's speaker/read-aloud control. Judge
   intelligibility, pauses and volume. Stop playback with its on-screen control;
   check that you can tell it stopped.

**Pass when:** the important words are accurate in both attempted conditions,
speech is understandable, typed work survives cancellation/device loss, and
recording/playback end as expected. Record a wrong day, time or missing “not”
as an accuracy failure even if the sentence sounds plausible. If you cannot
judge whether recording stopped, report that uncertainty rather than a pass.

**Return:** microphone/headset name, language/accent if you wish, room conditions,
what you said, what appeared and what you heard. Capture only the synthetic
draft. Do not include background conversations. Hands-free **Talk** is a Preview
and is not qualified by passing this dictation/read-aloud check.

## 6. H-04 — Your account sign-in, consent and revocation

**Allow:** 15–20 minutes per assigned service. **Needs:** a prepared connector,
a consenting account owner and a harmless test account/fixture. Skip services
the coordinator has not assigned. **Why a person:** only the account owner can
give informed consent, complete their own MFA/security-key challenge and judge
whether the account and requested permissions are acceptable.

1. Ask the coordinator for the exact service name, test account, allowed
   permissions and how to revoke access on that service. They must have already
   registered/configured the application. If not, mark **Blocked**; do not
   create a developer application or enter somebody else's credentials.
2. In Raiker, open **Connections → Services → Add connection**. Select the
   assigned service and follow **Connect/Sign in**. If its name or entry point
   differs from your supplied pack, stop and record the mismatch.
3. On the service's own sign-in page, check that you recognise the service and
   intended account. Complete your password/MFA/security-key steps yourself.
   Do not send codes, passwords or recovery codes to the coordinator or an AI.
4. Before consenting, read the requested permissions. Compare them with the
   coordinator's written list. Decline and report **Fail** if they are broader,
   unclear or name the wrong account. Do not grant extra access to continue.
5. If the request is acceptable, consent and return to Raiker. Check that the
   connected account's visible name is correct. Explain in your own words what
   you think Raiker may now read or change.
6. Let the coordinator run the separately prepared harmless verification, if
   assigned. You do not need to construct API requests, inspect tokens or
   troubleshoot provider errors. Observe whether any approval clearly names
   the account, destination and proposed effect. Do not authorise a real send.
7. Revoke access using the service's own account-security/connected-apps page,
   following the coordinator's service-specific instructions. Confirm you
   understand which application/account you are revoking. Have the coordinator
   verify that the next protected action is refused rather than silently
   switching accounts. Record their verification separately from your consent check.

**Pass when:** you can identify the account and permission scope, decide
knowingly, complete your own authentication and find/understand revocation.
The coordinator's automated refusal/read-back test must also have its own
result; your consent check alone does not qualify the connector lifecycle.

**Return:** service name, permission descriptions, confusing or unexpected
prompts and whether revocation was understandable. Redact account addresses
and all codes. Missing OAuth setup is **Blocked**, not a tester mistake.

## 7. H-05 — Readability on your actual PC display

**Allow:** 10–15 minutes. **Needs:** your normal monitor and usual glasses or
assistive display settings. **Why a person:** a screenshot at a simulated width
cannot establish physical readability, comfort or focus visibility for you.

1. Record your Windows display scaling (for example 100%, 125% or 150%) and
   Raiker window size: maximised or your normal working size. The coordinator
   can help find these; you do not have to change system settings.
2. Open Chat, read an answer, then open Approvals and Settings. Can you read
   text, distinguish controls and see the current keyboard focus comfortably?
3. Make the Raiker window narrower using its edge. Can you still find the
   navigation and use the page without labels or actions being cut off?
4. Increase text/page zoom if supported by this build and you normally need it.
   Record how you did so and the value. If a needed zoom control is absent,
   report that fact; do not change hidden browser flags.
5. If the coordinator assigned another display scale or light/dark appearance,
   repeat steps 2–3 there, then restore your original setting. Otherwise record
   it as **Not tested**. Phones, tablets and macOS are outside this Windows check.

**Pass when:** you can comfortably read the important information, distinguish
states without relying only on colour, see focus and reach actions at your
assigned settings. Record eyestrain, ambiguous icons and clipped content even
when you can eventually work around them.

## 8. H-06 — Personal acceptance decision

**Allow:** 5–10 minutes. **For:** the tester and, separately, the release owner.
This is a human judgment, not a checkbox an automated agent can sign for you.

1. Review your results. Name anything you did not test or could not complete.
2. Answer: “Would I use this build for the limited personal tasks I tested?”
   Choose **Yes**, **Yes with stated limits**, or **No**, and give your reasons.
3. Describe any moment you did not know what Raiker was doing, where your
   information was going, what a button would change or whether work had stopped.
4. Send the report privately to the coordinator. The release owner combines
   these observations with engineering evidence and open defects, and records
   their own decision. Your “Yes” does not authorise a public release or waive
   an unresolved privacy/security defect.

## 9. Copy this report for each assigned check

```text
Tester identifier:
Date/time and time zone:
Raiker version/build from the supplied test pack:
Windows version; display scaling; window size:
Check ID and attempted step numbers:
Result: Pass / Fail / Blocked / Not tested
Expected result:
What actually happened (include exact words if useful):
Steps that reproduce the problem:
Model/service/equipment used (names only, no credentials):
Test content/fixture used; any spending or time limit reached:
Help, coaching, retries or workarounds received:
Start/end time or approximate duration:
Redacted screenshot/optional consented recording filenames:
Remaining steps and why they were not attempted:
Personal acceptance choice, if H-06:
```

Use **Win+Shift+S** to capture the relevant part of the screen if convenient.
Check it for passwords, keys, MFA codes, email addresses and unrelated personal
content before sending. Feedback opened on GitHub can be public: use the
coordinator's private contact for these test reports.

## Coordinator notes and engineering ownership

This is the human-only companion to [the testing plan](../plans/TESTING.md),
not a replacement for it. Link returned results to their exact candidate and
to T-01/T-14 (understanding/accessibility), VD-1/V-01 (physical audio), approved
connector consent, UX readability and the owner's acceptance decision.
The [personal scope](../plans/PERSONAL_BETA_SCOPE.md) is at most five users,
PC first. This guide does not introduce a mandatory three-person study.

Do not assign the following as novice “human-only” tests: BUG-360's legacy
memory provenance, native account/ACL or directory races, Apply/rollback,
provider fault injection, automated installer/data-retention mechanics,
packet-level egress capture, CI, Ruff, lint or mypy. The agent/development team
can implement or test those. Missing OAuth clients, test fixtures or candidate
builds are preparation blockers to resolve, not evidence that only a person
can test the underlying feature. Keep those items in
[the open ledger](../plans/TO_BE_FIXED.md).

Record each returned human report as **not run** until actually performed;
preserve failed and blocked attempts. Do not infer physical microphone,
screen-reader or account-consent acceptance from generated audio, screenshots,
accessibility scans or the existence of this guide.
