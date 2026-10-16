# BetBonus — Offensive Scale Plan

## Objective

Transform BetBonus from a **detection + semi-automated test harness** into a **fully automated multi-account bonus→cash extraction engine** that scales gains across platforms while remaining undetected.

---

## Current State (What Works)

| Layer | Status | Gap |
|-------|--------|-----|
| Identity generation | ✅ Synthetic BR identities (valid CPF/CNH, DDD mapping, BR emails) | No behavioral fingerprint diversity, no document images, no SMS interception |
| Proxy rotation | ✅ ProxyPool round-robin | No geo-consistency per identity, fixed delays (not randomized) |
| Registration | ✅ Pagol OAuth, 4play JSON | 4play SPA registration unverified at scale |
| Auth | ✅ OAuth password/refresh, HMAC tokens | Token refresh not automated for long sessions |
| Bonus acquisition | ✅ Promocode redeem API + claim_all_bonuses() | Manual BO credit still needed for some offers |
| Game launch | ✅ Salsa URL → provider iframe (both scrapers) | **No programmatic spin/bet** (Chromium click only, max 20) |
| Wagering | ⚠️ Chromium click (1-20 spins, provider default stake) | No stake control, no variance management, no loop, no adaptive stop |
| Balance monitoring | ✅ Wallet API polling (get_wallet_snapshot) | No adaptive stop conditions, no live rollover tracking |
| Withdrawal | ✅ PIX API + settlement polling (5s interval, 90s timeout) | No timing optimization, no multi-account stagger, no split strategy |
| Kill chain | ✅ 9-stage pipeline (recon→auth→discovery→acquire→arm→analyze→probe→cashout→report) | Wagering stage is SEMI_AUTO bottleneck |
| Multi-account | ✅ AccountFactory batch (register→login→kill_chain) | No staggered timing, no P&L tracking, sequential execution |
| Stuck-point diagnosis | ✅ diagnose_withdraw_stuck() (4 failure classes) | No auto-retry, no escalation path |
| Reporting | ✅ Journey sessions, markdown+JSON reports, remediation plan (P0/P1/P2) | No cross-account P&L dashboard |
| LLM assist | ✅ IronLLMClient + AbuseLLMAssist (T&C → RulesCanon + vectors) | Not used for game selection or adaptive strategy |
| Risk models | ✅ sims.py (blackjack H17, baccarat EV, roulette ruin, crash EV) | Offline only, not wired into wagering loop |

---

## The 5 Bottlenecks to Solve

### 1. Game Play Automation (CRITICAL)

**Problem:** The only way to wager bonus is Chromium clicking the spin button (max 20 clicks). Too slow, too visible, doesn't scale.

**Solution — 3-tier approach:**

| Tier | Method | When to use | Speed |
|------|--------|-------------|-------|
| 1 | API-level auto-bet | Provider exposes REST/WS bet endpoint | 100+ bets/min |
| 2 | WebSocket protocol replay | Provider uses WS for game logic | 50-100 bets/min |
| 3 | Optimized headless browser | No API access, must click UI | 20-50 bets/min |

**Tier 1 — API Auto-Bet:**
- Intercept the WebSocket/REST in the Chromium session (already captured in `inspect_launch`)
- Parse the bet/stake message format from the provider's JS bundle
- Replay: `POST /api/bet {gameId, stake, seed, token}` or WS `send {action: "spin", stake: 1.0}`
- No browser needed after initial launch — pure HTTP/WS

**Tier 2 — WebSocket Protocol Replay:**
- Launch game once via Chromium → capture the WS handshake + first spin message
- Extract the auth token, game session ID, message schema
- Build a standalone WS client that sends N spins with configurable stake
- No browser in the loop after initial capture

**Tier 3 — Optimized Headless Browser (Fallback):**
- Persistent Chromium context (not fresh launch per game)
- Pre-warmed iframe (game already loaded, just click spin)
- Batch: 50-200 spins per session with 300-800ms intervals
- Stake via UI manipulation (set bet amount field before clicking)
- Parallel: 4-8 browser contexts per machine

**New files:**
- `src/integrity/ws_replay.py` — GameWSClient (intercept + replay)
- `src/integrity/browser_farm.py` — BrowserFarm (persistent multi-context)
- `src/scrapers/pagol_scraper.py` → new method `api_auto_bet(game_id, stake, rounds)`
- `src/abuse/matrix.py` → wagering stage calls engine instead of Chromium

---

### 2. Wagering Strategy Engine

**Problem:** No adaptive strategy. Need to clear rollover with minimum risk while staying under max-bet and game-type restrictions.

**Solution — `WageringStrategyEngine` (`src/abuse/wagering.py`):**

**Key insight:** For bonus→cash, the optimal strategy is NOT "win big." It's:
- Use **low-variance, high-RTP games** (Mines 1x = 99% RTP, Aviator 1.01x cashout)
- Stake at **max_bet** to minimize number of rounds needed
- Accept ~5% house edge over N rounds
- Stop immediately when `remaining_rollover ≤ 0`

**Algorithm:**
1. Prefer high-RTP crash games (Mines 1x, Aviator 1.5x cashout) → near-deterministic
2. Stake = min(max_bet, bonus_balance / target_rounds)
3. If RTP < 95%: increase stake to clear faster (accept variance)
4. If max_bet < 1.0: must use many small bets (time cost)
5. Switch games if one hits a losing streak > 3σ

**Example math (Pagol):**
- Bonus: R$50, rollover: 5x = R$250 wagered, Max bet: R$5
- Game: Mines (1 mine, 99% RTP)
- Rounds needed: 250 / 5 = 50 rounds
- Expected loss: 50 × 5 × 0.01 = R$2.50 (5% of bonus)
- Net extractable: R$47.50 (before withdrawal cap)
- Time: 50 × 0.5s = 25 seconds (API) or 50 × 3s = 2.5 min (browser)

---

### 3. Multi-Account Orchestration at Scale

**Problem:** AccountFactory runs sequentially. No timing stagger, no P&L tracking.

**Solution — `ScaleOrchestrator` (`src/factory/scale_orchestrator.py`):**

```
run_campaign():
  1. Register N accounts (staggered: 5-15 min apart)
  2. For each account:
     a. Wait for bonus to activate (if time-gated)
     b. Execute wagering strategy
     c. Wait for rollover to clear
     d. Withdraw (staggered: different hours)
     e. Track P&L
  3. If withdrawal denied → flag for manual review
```

**Anti-correlation rules:**
- Accounts register at different times (not same minute)
- Different proxy IPs per account (geo-consistent: BR IP + BR phone DDD)
- Wagering sessions at different times of day
- Withdrawals spread over 2-3 days
- No two accounts withdraw in the same 30-min window
- Identity attributes consistent (SP phone → SP address → SP IP)

**New files:**
- `src/factory/scale_orchestrator.py` — campaign planning, scheduling
- `src/factory/scheduler.py` — TimingScheduler (staggered events)
- `src/factory/pnl.py` — P&L Tracker (per-account, per-campaign)
- `src/factory/behavior.py` — BehavioralFingerprint (per-account timing/stakes)

---

### 4. Anti-Detection Layer

**Problem:** Bulk automated activity looks like a bot farm. Need behavioral realism.

**Solution — `BehavioralFingerprint` (`src/factory/behavior.py`):**

Per-account behavioral profile:
- `session_duration()`: 10-90 min (log-normal)
- `inter_bet_delay()`: 0.8-4.0s (Gaussian, mean 2s)
- `bet_stake_sequence(n)`: 70% same, 20% ±1 step, 10% jump
- `idle_gaps()`: 3-8 minute pauses during a session
- `daily_activity_window()`: active 19:00-23:00 (not 03:00-05:00)

**Network layer:**
- One proxy per identity (not shared)
- Geo: IP country = BR, city ≈ address city, DDD matches
- TLS fingerprint: use `curl_cffi` or `tls-client` to match Chrome 120+

**Temporal layer:**
- Registration: weekday 14:00-22:00 BR time
- First deposit: 1-6 hours after registration
- Wagering: 20-72 hours after bonus activation
- Withdrawal: 24-96 hours after rollover completes

---

### 5. Withdrawal Orchestration

**Problem:** Withdrawal timing and amount can trigger BO review.

**Strategy:**
- **Amount:** Withdraw ~95% of `max_convert_brl` (not the exact cap)
- **Split:** If balance > R$1000, do 2 withdrawals 24-48h apart
- **Timing:** 48+ hours after last wager, during 10:00-16:00 BR (business hours)
- **Method:** PIX to own CPF (not third-party)
- **Frequency:** Max 1 withdrawal per 72h per account
- **Pattern:** First withdrawal smaller (R$50-100), second gets the rest

**New file:** `src/abuse/withdraw_orchestrator.py` — plan + execute withdrawals

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SCALE ORCHESTRATOR (new)                      │
│  run_campaign() → register → wager → withdraw → track P&L      │
├─────────────────────────────────────────────────────────────────┤
│  Account Factory (existing)  │  Wagering Engine (new)          │
│  Identity + Proxy + Behavior │  Game Play Layer (new)          │
│  (extended)                  │  Tier 1: API / Tier 2: WS       │
│                              │  Tier 3: Browser Farm           │
│  Withdraw Orchestrator (new) │  P&L Tracker (new)              │
│  KillChainMatrix (modified)  │  Campaign Dashboard (new FE)    │
│  LLM Assist (existing)       │                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Wagering Engine (Week 1-2)

**Goal:** Clear rollover programmatically without Chromium.

| Task | File | Effort |
|------|------|--------|
| WS intercept + replay for Spribe | `src/integrity/ws_replay.py` | 3d |
| API auto-bet for Pragmatic | `src/scrapers/pagol_scraper.py` | 2d |
| WageringStrategyEngine | `src/abuse/wagering.py` | 2d |
| Modify KillChainMatrix wagering stage | `src/abuse/matrix.py` | 1d |
| Browser farm (persistent context) | `src/integrity/browser_farm.py` | 2d |
| Tests: verify rollover clears | `tests/test_wagering.py` | 1d |

**Deliverable:** `matrix.run(auto_bet=True, wager_rounds=50)` clears R$250 rollover in < 2 min.

### Phase 2: Scale Orchestrator (Week 3-4)

**Goal:** Run 10-50 accounts across 2-3 platforms with staggered timing.

| Task | File | Effort |
|------|------|--------|
| ScaleOrchestrator | `src/factory/scale_orchestrator.py` | 3d |
| BehavioralFingerprint | `src/factory/behavior.py` | 2d |
| TimingScheduler | `src/factory/scheduler.py` | 1d |
| P&L Tracker | `src/factory/pnl.py` | 1d |
| Modify AccountFactory | `src/factory/account_factory.py` | 1d |
| API endpoint: campaign run | `src/api.py` | 1d |
| Tests: batch of 10 | `tests/test_scale.py` | 1d |

**Deliverable:** `orchestrator.run_campaign(accounts=20, platforms=["pagol","4play_br"])` → P&L report.

### Phase 3: Anti-Detection + Withdrawal (Week 5-6)

**Goal:** Stay under BO radar, optimize withdrawal timing.

| Task | File | Effort |
|------|------|--------|
| WithdrawOrchestrator (plan + execute) | `src/abuse/withdraw_orchestrator.py` | 2d |
| TLS fingerprint (curl_cffi) | `src/factory/tls.py` | 1d |
| Temporal scheduling (real-time waits) | `src/factory/scheduler.py` | 1d |
| BO denial detection + retry logic | `src/abuse/withdraw_orchestrator.py` | 1d |
| Campaign dashboard (frontend) | `dashboard-v2/src/...` | 2d |
| E2E test: full campaign, 5 accounts | `tests/test_e2e_campaign.py` | 2d |

**Deliverable:** 5-account campaign runs unattended over 72h, all withdrawals materialize.

### Phase 4: Optimization + Scaling (Week 7-8)

**Goal:** Maximize throughput, add adaptive decision-making.

| Task | File | Effort |
|------|------|--------|
| LLM-driven game selection (RTP + variance) | `src/abuse/wagering.py` | 2d |
| Adaptive stake (adjust based on live balance) | `src/abuse/wagering.py` | 1d |
| Multi-provider parallel (Spribe + Pragmatic + PG) | `src/integrity/browser_farm.py` | 2d |
| Campaign auto-retry (failed accounts) | `src/factory/scale_orchestrator.py` | 1d |
| Real-time P&L dashboard (WebSocket) | `dashboard-v2/src/...` | 2d |
| Scale to 100+ accounts (resource pooling) | `src/factory/scale_orchestrator.py` | 2d |

**Deliverable:** 100-account campaign, R$5000+ extracted, zero BO denials.

---

## Key Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Provider changes WS protocol | Tier 3 browser fallback always available |
| BO flags bulk withdrawals | Stagger timing, split amounts, business hours |
| Account banned before withdrawal | Wager slowly (20-72h window), withdraw early |
| Proxy IP flagged | Use residential proxies (Bright Data/Oxylabs), 1 per identity |
| CPF reuse detected | Generate unique valid CPFs, never reuse |
| Platform adds CAPTCHA | Playwright handles CAPTCHA via `puppeteer-extra-plugin-stealth` |
| Bonus T&C change mid-campaign | LLM re-analysis before each wagering phase |

---

## Expected ROI

**Per account (Pagol, R$50 bonus, 5x rollover):**
- Gross bonus: R$50
- House edge loss (50 rounds × 1%): R$2.50
- Net extractable: ~R$47
- Withdrawal: R$45 (95% of max)
- **Net profit: R$45 per account**

**Campaign of 20 accounts × 3 platforms:**
- 60 accounts × R$45 = **R$2,700 extracted**
- Cost: ~R$200 in proxies + R$50 in deposits (if required)
- **ROI: ~90%**
- Time: 72 hours (staggered)

**Scaling to 100 accounts × 5 platforms:**
- 500 accounts × R$45 = **R$22,500 extracted**
- Time: 2-3 weeks (staggered)
- **ROI: ~85%** (proxy costs increase)

---

## Verified Gaps (from code analysis — 2026-09-14)

Confirmed by deep code review of both scrapers, matrix, stages, oracle, factory, and integrity modules:

### What does NOT exist (must be built):

| Gap | Evidence |
|-----|----------|
| No WS protocol replay | `player.py` docstring: "Does NOT decode spin protocol (Pragmatic gs2c, Patagonia, Spribe SmartFox)" |
| No bet-size manipulation | `auto_bet()` uses provider default stake; no UI field manipulation |
| No stake control in wagering | `run_bonus_multiplier_lab` caps at `MAX_LAB_STAKE_BRL=5.0`; no dynamic stake adjustment |
| No loop beyond 20 clicks | `AUTO_BET_MAX_CLICKS=20` hard cap in `inspect_launch` |
| No adaptive stop conditions | No `remaining_rollover` tracking in the wagering loop |
| No game selection strategy | `_bonus_play_strategy()` computes the path but doesn't execute it adaptively |
| No behavioral fingerprint | Single fixed User-Agent, no timing jitter, no per-account patterns |
| No geo-consistent proxy binding | ProxyPool is round-robin, not identity-bound |
| No document image generation | No fake CNH/CPF scans for KYC upload |
| No SMS interception | No phone verification bypass |
| No TLS fingerprint rotation | Single `curl`-like fingerprint for all requests |
| No CAPTCHA handling | Not implemented |
| No P&L tracking | No cross-account profit/loss aggregation |
| No campaign scheduler | No real-time staggered event scheduling |
| No withdrawal split strategy | Single withdrawal per account, no multi-draw pattern |
| No auto-retry on BO denial | `diagnose_withdraw_stuck()` classifies but doesn't retry |
| No live rollover polling during wager | Wallet polled after N clicks, not per-bet |

### What EXISTS and can be leveraged:

| Capability | Location | How to leverage |
|-----------|----------|-----------------|
| `probe_high_ev_contribution()` | Both scrapers | Identify eligible games before wagering |
| `_bonus_play_strategy()` | `pagol_scraper.py:390-440` | Compute optimal path (slots vs high-EV vs restricted) |
| `run_bonus_multiplier_lab()` | Both scrapers | Existing lab harness to extend with loop + stake control |
| `inspect_launch()` | `integrity/player.py` | Already captures requests/websockets — extend for WS replay |
| `get_wallet_snapshot()` | Both scrapers | Per-bet rollover tracking |
| `diagnose_withdraw_stuck()` | `auto_journey.py:437-590` | 4 failure classes → auto-retry logic |
| `classify_conversion()` | `oracle.py:25-120` | 5 wallet states → adaptive stop conditions |
| `sims.py` risk models | `integrity/sims.py` | Wire into wagering engine for EV calculations |
| `claim_all_bonuses()` | `auto_journey.py` | Batch redeem + activate before wagering |
| `build_remediation_plan()` | `auto_journey.py:590-700` | P0/P1/P2 → exploit priority ordering |
| LLM `RECON_SYSTEM_PROMPT` | `house_profile.py` | Per-house exploit surface → game selection |
| `KillChainMatrix` 9 stages | `matrix.py` | Extend arm stage from SEMI_AUTO → AUTOMATED |

### Dominant Blocker Priority (from `_dominant_blocker()`):

The 10 vulnerability identifiers in priority order tell us exactly what to fix first:

1. `session_expired` → Token refresh automation
2. `withdraw_ok_api_but_bo_denied` → Timing + amount optimization
3. `repeated_bo_denied_on_cash_withdraw` → Split withdrawals, stagger
4. `rollover_gate_caps_extractable_value` → **Wagering engine (PRIMARY)**
5. `high_ev_launch_ok_but_bonus_game_type_blocks_stake` → Game type filtering
6. `have_opened_blocks_new_withdraw` → Sequential withdrawal scheduling
7. `withdrawal_not_allowed` → Profile-level gate (wait/retry)
8. `bo_credit_or_manual_claim_required` → Manual escalation path
9. `awaiting_manual_stake` → **Auto-bet (PRIMARY)**
10. `slots_bonus_launch_ok_spin_manual` → Browser farm fallback

**The two PRIMARY blockers (#4 and #9) are both solved by the Wagering Strategy Engine + Game Play Automation layers.**
