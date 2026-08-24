# Holoscrape — Complete Code Review

Date: 2026-08-24
Reviewer: lusterpixie

## TL;DR

The core pipeline (index → scrape → write) works, but the codebase has a
cluster of bugs that will bite in production, a logging layer that's
effectively broken, no error recovery, and an architecture that's hard to
extend. It's a functional prototype that needs a proper pass before it's
reliable.

---

## 1. Active Bugs

### 1.1 Logger silently drops INFO messages
`modules/logger/base.py:13` calls `logging.basicConfig(filename=..., level=logging.WARNING)`.
This attaches a `FileHandler` at WARNING level to the **root logger**. Then
line 15 calls `self.logger.setLevel(logging.INFO)` on a **named** logger.
The named logger passes INFO records to the root handler, which filters them
out at WARNING. Net result: only WARNING+ messages reach the file, despite
the code appearing to log at INFO.

Fix: create a dedicated `FileHandler` with the correct level on the named
logger, or set the root handler level to the intended value.

### 1.2 `logging.basicConfig` is a no-op after first call
`basicConfig` only configures the root logger if it has no handlers. In a
long-running process (main.py or multiple scrapers in tmux), the second and
subsequent `createLogger` calls create loggers that write to the **first**
log file, not their own. Each scraper's log entries go to the first
scraper's file.

### 1.3 Missing log directory crash
`scrape.py` calls `createLogger(...)` which does `open(log_path, 'a+')`.
If the directory doesn't exist (e.g. first run, fresh deploy), it crashes
with `FileNotFoundError` before doing anything useful. `main.py` creates
the directory but `scrape.py` does not.

### 1.4 `FilesystemWriter.process_stream` called on an instance without `self.file`
In `main.py:38`, `FilesystemWriter(config_handler, None)` is constructed
with `video_id=None`. The `__init__` only sets `self.file` if `video_id` is
truthy. `process_stream` doesn't use `self.file` so it works, but if
`process()` is ever called on that instance it's an `AttributeError`.

### 1.5 Off-by-one in flush counter
`FilesystemWriter.process` flushes when `self.counter == 10` **before**
incrementing. So it flushes on the 11th message, not the 10th. Minor but
the intent is clearly "flush every 10".

### 1.6 `retries` counter never resets in `scrape.py`
The `retries` counter in `Scrape.run()` accumulates across the entire
stream lifetime. After 5 total reconnection attempts (spread over hours),
the scraper gives up permanently even if each reconnection was successful.
It should reset after a successful reconnection or use a sliding window.

### 1.7 Bare `except:` in indexers
`holodex.py:14` and `nijidex.py:14` use bare `except:` which catches
`KeyboardInterrupt`, `SystemExit`, and all other exceptions. Should be
`except requests.RequestException`.

### 1.8 No timeout on HTTP requests
`requests.get(...)` in both indexers has no `timeout=` parameter. A hung
connection will block the poll loop forever.

### 1.9 `main.py` log file handle never closed
`main.py:20` opens `main.log` with `open(..., "a+")` and never closes it.
Over a long-running process this is a file descriptor leak (though in
practice the OS will clean up on exit).

### 1.10 SQL `source` column grows unboundedly
`DatabaseWriter.post()` uses `ON DUPLICATE KEY UPDATE source =
CONCAT(source, ' {hostname}')`. If the same chat_id is seen by multiple
hosts (or the same host reconnects), the source column grows without
bound. No length cap.

---

## 2. Code Quality / Refactoring

### 2.1 Duplicate `now()` function
Defined identically in both `main.py` and `scrape.py`. Should be a shared
utility.

### 2.2 HolodexIndexer and NijisanjiIndexer are 95% identical
The only differences are the `org` query param and the EN filter. Should be
a single `HolodexIndexer` with an `org` and optional `filter` parameter, or
a shared base with a `_filter(stream)` hook.

### 2.3 `base.py` (indexer) imports `requests` but never uses it
Dead import.

### 2.4 `DatabaseWriter.threads = []` declared but never used
Dead code.

### 2.5 No type hints
Only `base.py` (indexer) has a return type hint. Everything else is
untyped. For a project targeting Python 3.14 this is a missed opportunity.

### 2.6 No docstrings
No module, class, or method has a docstring. The README is the only
documentation.

### 2.7 No `__init__.py` files
`modules/`, `modules/indexer/`, `modules/logger/`, `modules/writer/` all
rely on Python 3 namespace packages. This works but is fragile with some
test runners, linters, and packaging tools. Add explicit `__init__.py`.

### 2.8 `requirements.txt` has no version pins
Four dependencies, none pinned. `pytchat` in particular is a small
community package that could break without notice.

### 2.9 `print()` mixed with logging
`scrape.py:76` has `print(self.video_id, idx, c.message)` — debug output
left in production. `DatabaseWriter.post()` also uses `print()` alongside
`self.logger.info()`.

### 2.10 Inconsistent Writer API
`Writer.process(chat)` handles individual messages.
`Writer.process_stream(stream)` handles stream metadata.
But `process_stream` is **not** defined in the base class — it only exists
on concrete writers. And in `main.py`, the writer instance is used
differently than in `scrape.py` (main calls `process_stream`, scrape calls
`process`). The base class should define both as no-ops.

### 2.11 `ConfigHandler` uses bare dict access
`data['write_to_db']` will throw `KeyError` on missing keys. Should use
`.get()` with sensible defaults, or validate the schema upfront.

### 2.12 `randint(30, 100)` for DB batch size
Non-deterministic batch sizing is bizarre. Should be a config value with a
sensible default (e.g. 50).

### 2.13 `validate_configs` pattern is inverted
The base `Writer.__init__` calls `self.validate_configs(c)` and raises a
bare `Exception()` on failure. The subclass implements the check. This
means the base class constructor can fail for subclass-specific reasons —
a confusing contract. Better: let each subclass validate in its own
`__init__` after `super().__init__()`.

---

## 3. Architecture

### 3.1 Hardcoded indexer and writer lists in `main.py`
`main.py:31` hardcodes `(HolodexIndexer, NijisanjiIndexer)`. Adding a new
indexer requires editing `main.py`. Should be config-driven (list of
indexer class names or module paths).

### 3.2 No way to run scrapers without tmux
The entire scraping pipeline is gated behind tmux pane management. There's
no `--no-tmux` mode, no standalone scraper mode, no systemd-friendly mode.
`scrape.py` can run standalone (it's what the tmux panes execute) but the
entry point in `main.py` always creates tmux panes.

### 3.3 Synchronous blocking with `sleep(60)`
The main loop polls every 60 seconds with a hard sleep. The scraper polls
every 1 second. No async I/O. For a small number of streams this is fine,
but it doesn't scale. If you want to scrape 50 concurrent streams, you'd
have 50 tmux panes each sleeping 1s.

Consider: `asyncio` + `aiohttp` for the indexers, and let pytchat handle
its own polling (it already has an async mode in newer versions).

### 3.4 Two-tier process architecture is fragile
`main.py` spawns `scrape.py` as child Python processes in tmux panes.
There's no IPC, no health checking, no automatic respawn beyond the
"pane is dead" check. If a scraper crashes, the pane dies, and the next
poll cycle (up to 60s later) notices and respawns. This means:
- Up to 60s of lost data on crash
- No crash logging (the process just dies)
- The `url_to_pane` dict is the only state, lost on main.py restart

### 3.5 No graceful shutdown
Neither `main.py` nor `scrape.py` handles SIGTERM/SIGINT cleanly. `main.py`
has no signal handler at all. `scrape.py` catches `KeyboardInterrupt` but
only in the `__main__` block — if the exception is raised inside `run()`,
the `finalise()` calls are skipped.

### 3.6 Config is a flat dict
No namespacing. `db_*` keys are flat, `local_path` is flat, `log_path` is
flat. As the project grows (multiple indexers, multiple writer configs,
per-indexer filters), this will get unwieldy. Consider nested config or
pydantic models.

---

## 4. Missing Features / Improvements

### 4.1 No `poll_interval` config
The 60s sleep in `main.py` is hardcoded. Should be configurable.

### 4.2 No per-indexer configuration
Can't configure which orgs to track, which language filters to apply, or
which streams to exclude. All hardcoded in the indexer classes.

### 4.3 No stream filtering in config
Can't say "only scrape these channels" or "exclude these channels". The
only filter is the Nijisanji EN check (hardcoded).

### 4.4 No maximum concurrent streams limit
If 50 streams go live simultaneously, `main.py` will try to create 50 tmux
panes. No cap, no priority.

### 4.5 No retry/backoff on indexer failures
If the Holodex API is down, the indexer silently returns `[]` (due to the
bare except). The main loop sees no streams and sleeps 60s. No alerting,
no logging, no backoff.

### 4.6 No structured logging
All logs are unformatted strings. No JSON logs, no log levels per module,
no correlation IDs. For debugging a multi-stream setup this is painful.

### 4.7 No metrics / monitoring
No way to know how many messages have been scraped, how many are in the
DB buffer, how long the scraper has been running, etc.

### 4.8 No data quality checks
- What if `chat.message` is None? (System messages, etc.)
- What if `chat.author` is None?
- What if the stream ID from Holodex is malformed?
- No validation of chat data before writing.

### 4.9 No rotation for log files
Logs grow forever. No size-based or time-based rotation.

### 4.10 `init.sql` is 300 lines of copy-paste
30 identical table definitions. Should be a single `CREATE TABLE` + a
loop in a stored procedure, or better, generated by a migration tool
(Alembic, or just a Python script).

---

## 5. Testing Gaps

### 5.1 `holodex_indexer_test.py` hits the real API
This is an integration test in a unit test file. It will fail when the API
is down, rate-limited, or when no streams are live. Should mock
`requests.get`.

### 5.2 No tests for NijisanjiIndexer
The EN filter logic is untested.

### 5.3 No tests for the retry/reconnection logic in `scrape.py`
The most complex code in the project (the nested while loops in `run()`)
has zero test coverage.

### 5.4 No tests for `main.py` tmux management
The pane lifecycle (create, detect death, respawn, cleanup) is untested.

### 5.5 `database_integration_test.py` is brittle
Requires: a running MySQL, a valid Holodex API key, AND a live stream at
the moment the test runs. Any of those missing and it skips. The mock
`pytchat` is good but the Holodex call is real.

### 5.6 No test for `FilesystemWriter.process_stream`
The metadata writing path is untested.

### 5.7 No test for config validation
What happens when the config JSON is malformed? Missing required fields?
Wrong types?

### 5.8 No test for the logger
The logger bug (section 1.1) would have been caught by a simple test that
verifies INFO messages appear in the log file.

---

## 6. Suggested Priority Order

If I were doing this revision, I'd attack in this order:

1. **Fix the logger** (1.1, 1.2, 1.3) — this is broken today and makes
   debugging impossible.
2. **Add timeouts to HTTP requests** (1.8) and fix bare excepts (1.7) —
   these cause silent hangs.
3. **Remove debug prints** (2.9) and fix the flush off-by-one (1.5).
4. **Add config options** for poll interval, batch size, indexer selection
   (4.1, 2.12, 3.1).
5. **Merge the two Holodex indexers** into one parameterized class (2.2).
6. **Add `__init__.py` files**, type hints, docstrings (2.7, 2.5, 2.6).
7. **Pin dependencies** (2.8).
8. **Fix the retry logic** in scrape.py (1.6) and add proper signal
   handling (3.5).
9. **Rewrite the test suite**: mock HTTP calls, test the retry logic,
   test the logger, add config validation tests (section 5).
10. **Consider a `--no-tmux` mode** (3.2) so the scraper can run under
    systemd/supervisord without tmux.
11. **Generate `init.sql`** from a script instead of copy-paste (4.10).
12. **Add structured logging** with JSON output (4.6).

Longer-term (if the project is going to keep growing):
- Move to `asyncio` for the main loop and indexers.
- Replace the tmux-pane architecture with a proper process manager
  (or just run each scraper as a subprocess with `subprocess.Popen`
  and health-check it).
- Add a web UI or API for monitoring active scrapers.
- Use `pydantic` for config validation.
- Add a migration system for the DB schema.
