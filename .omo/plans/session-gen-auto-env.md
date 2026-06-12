# Auto-Fill Session Generator from .env

## Objective
Enhance `resources/session/ssgen.py` so it reads `API_ID` and `API_HASH` from the project's `.env` file when available, skips prompting for them, and automatically writes the generated `SESSION` back to `.env`. The launcher should no longer ask the user to manually paste the session string.

## Context
- `ssgen.py` currently always prompts for `API_ID` and `API_HASH`, even if they already exist in `.env`
- After generation, the `startup` launcher asks the user to copy/paste the session string manually
- Telethon/Pyrogram still need to interactively prompt for phone number and OTP — only the API credentials should be auto-prefilled

## Decisions
- **Auto-overwrite `SESSION`**: YES, with a printed confirmation message (per user request: "auto replaced")
- **Both Telethon & Pyrogram**: Update both paths in `ssgen.py` for consistency
- **No new dependencies**: Parse `.env` manually with shell-style logic; do not require `python-dotenv`

## Tasks

### Wave 1: ssgen.py Enhancements

- [x] 1. **Add `.env` reader to `ssgen.py`**
  - Resolve `.env` path relative to script location: `../../.env`
  - Parse simple `KEY=VALUE` lines, ignoring comments and blank lines
  - Strip optional surrounding quotes
  - Return dict of values
  - Handle missing `.env` gracefully

- [x] 2. **Auto-prefill `API_ID` and `API_HASH`**
  - Load credentials from `.env` before entering `telethon_session()` / `pyro_session()`
  - Pass them into `get_api_id_and_hash(api_id_default, api_hash_default)`
  - If a value exists, print "Using API_ID from .env" and skip prompt
  - If missing, fall back to existing interactive prompt
  - Keep validation (API_ID must be integer, API_HASH non-empty)

- [x] 3. **Auto-save `SESSION` to `.env`**
  - Add `save_session_to_env(session_string)` function
  - Read existing `.env` content; if `SESSION=` line exists, replace it in-place
  - If no `SESSION=` line exists, append `SESSION=<string>` ensuring trailing newline
  - If `.env` does not exist, create it with the `SESSION` line
  - Print clear confirmation: "SESSION saved to /path/to/.env"
  - Do not print the session string to terminal

- [x] 4. **Wire save into Telethon path**
  - After `ultroid.session.save()` succeeds, call `save_session_to_env()`
  - Remove or modify early `return` that bypasses save

- [x] 5. **Wire save into Pyrogram path**
  - After `pyro.export_session_string()` succeeds, call `save_session_to_env()`
  - Remove `exit(0)` that prevents returning to launcher menu

- [x] 6. **Clean up loop behavior**
  - Remove "Run again?" loop or make it launcher-controlled
  - Ensure script exits with code `0` on success, non-zero on error
  - The launcher should be able to call `python3 resources/session/ssgen.py` once and return to menu

### Wave 2: Launcher Integration

- [x] 7. **Update `startup` `generate_session()` function**
  - After running `python3 resources/session/ssgen.py`, check exit code
  - On success: reload `.env`, print "SESSION saved to .env", refresh env status
  - On failure: print error and return to menu
  - Remove the manual "Save generated SESSION? [y/N]" prompt
  - Remove the manual "SESSION: " paste prompt

- [x] 8. **Update launcher menu status after session gen**
  - After successful generation, show updated env status (SESSION should now be ✅)
  - Prompt "Press Enter to return to menu" (existing `pause` behavior)

### Wave 3: Verification

- [x] 9. **Test happy path**
  - ✅ `load_env_file` and `save_session_to_env` verified via Python unit test
  - ✅ Verified no API_ID/API_HASH prompts when values present (code path confirmed)
  - ✅ Verified SESSION auto-write to .env (tested append, replace, no-trailing-newline cases)
  - ✅ Launcher returns to menu without manual paste (startup diff confirmed)

- [x] 10. **Test fallback path**
  - ✅ Verified prompt fallback logic in `get_api_id_and_hash()` (code path confirmed)
  - ✅ Verified auto-save still fires after successful generation (both Telethon & Pyrogram paths)

## Verification Commands
```bash
# Syntax check
python3 -m py_compile resources/session/ssgen.py

# Shellcheck startup (if installed)
shellcheck startup || true

# Manual flow test
bash startup
# Choose [7] Generate Session
```

## Files to Modify
- `resources/session/ssgen.py`
- `startup`

## Success Criteria
- [x] `ssgen.py` reads `API_ID`/`API_HASH` from `.env` and skips prompts when present
- [x] Generated `SESSION` is automatically written back to `.env`
- [x] Launcher returns to menu without asking user to paste session
- [x] Missing credentials still fall back to manual prompts
- [x] Both Telethon and Pyrogram paths updated
