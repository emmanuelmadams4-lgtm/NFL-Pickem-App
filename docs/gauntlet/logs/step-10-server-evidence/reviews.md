# Step 10 server: review fan-out at d4bf199 (read-only agents, 2026-10-13)

## ecc:python-reviewer — no CRITICAL, no HIGH
* MEDIUM 1: a stranger can keep the shared rate window or the 50 live sign-in challenges full, so the owner gets 429.
  **Carried, accepted**: design section 7 and owner decision 8 already say so (Dwight agreed; the token still works).
  A per-address limit is not possible behind Tailscale Serve without trusting forwarded headers.
* MEDIUM 2: the lazy import of `require_token` in `api/passkey.py` and `passkey_api.sessions` in `main.py` are fragile.
  **Carried**: the lane's grant in `main.py` is one import line; the same pattern is in `api/group.py`. Seam note.
* LOW 3: list, remove and sign-out answered 503 when the settings are unset. **Fixed** (P1 amended, work order 2).
* LOW 4: the 10-passkey limit is check-then-insert. **Comment added** (owner-only route).
* LOW 5: loose type hints. **Fixed** in CLEANUP.
* LOW 6: `sessions.accepts` raises `HTTPException`. **Carried**: keeps `require_token` inside its 10-line grant.
* LOW 7: `_alert` calls the private `push._send`/`_record`. **Carried as a SEAM** for the integrator.
* Checked and found correct: session handling with `expire_on_commit=False`, one commit for the sign-in update and the
  session, burn by `DELETE ... RETURNING`, sync/async split, model and migration match, constant-time compares.

## ecc:pr-test-analyzer — no vacuous test; three weak spots, all closed
* P16 window never tested (every test reset it). **Added** `test_p16_the_rate_window_slides`.
* P5 register side only tested replay after success. **Added** `test_p5_a_failed_registration_finish_also_uses_up_the_challenge`.
* P5 atomicity untested. **Added** `test_p5_finishes_racing_on_one_challenge_spend_it_once`.
* P15 did not drive refused registrations, 413 or 403. **Extended** `test_p15_nothing_secret_is_logged`.
* A removal that removes nothing must alert nobody. **Added** to `test_r2_adding_and_removing_a_passkey_alerts_the_owner`.

Not run here, with the reason: `ecc:security-reviewer` and `ecc:silent-failure-hunter` are run by Dwight on the code
commit (his report is `dwight-code-review.md`); `ecc:code-reviewer` is the fresh critic at VERIFICATION.
