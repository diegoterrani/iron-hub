"""
Campaign runner — orchestrates full multi-account campaigns with
auto-retry for failed accounts and parallel execution across providers.

Wraps ScaleOrchestrator + WageringStrategyEngine + WithdrawOrchestrator
into a single run_campaign() call.
"""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from src.factory.identity import Identity

log = logging.getLogger("betbonus.factory.campaign")

# Stage constants
STAGE_REGISTERED = "registered"
STAGE_BONUS_CLAIMED = "bonus_claimed"
STAGE_WAGERING = "wagering"
STAGE_WAGERED = "wagered"
STAGE_WITHDRAWN = "withdrawn"
STAGE_FAILED = "failed"
STAGE_PENDING = "pending"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Config & result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CampaignConfig:
    """Configuration for a multi-account bonus extraction campaign."""

    accounts: int = 10
    platforms: list[str] = field(default_factory=lambda: ["pagol_bet_br"])
    stagger_minutes: int = 10
    max_parallel: int = 4
    retry_failed: bool = True
    max_retries: int = 2
    wager_method: str = "api"  # "api" | "ws" | "browser"
    withdraw_split: bool = True
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "accounts": self.accounts,
            "platforms": self.platforms,
            "stagger_minutes": self.stagger_minutes,
            "max_parallel": self.max_parallel,
            "retry_failed": self.retry_failed,
            "max_retries": self.max_retries,
            "wager_method": self.wager_method,
            "withdraw_split": self.withdraw_split,
            "dry_run": self.dry_run,
        }


@dataclass
class CampaignAccountStatus:
    """Status of a single account within a campaign."""

    account_id: str
    platform: str
    identity_name: str
    identity_email: str = ""
    identity_cpf: str = ""
    identity_password: str = ""
    identity_phone: str = ""
    identity_birth_date: str = ""
    identity_address: str = ""
    identity_city: str = ""
    identity_state: str = ""
    stage: str = STAGE_PENDING
    error: str = ""
    balance: float = 0.0
    bonus: float = 0.0
    withdrawn: float = 0.0
    attempts: int = 0
    timestamps: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "platform": self.platform,
            "identity_name": self.identity_name,
            "identity_email": self.identity_email,
            "identity_cpf": self.identity_cpf,
            "identity_password": self.identity_password,
            "identity_phone": self.identity_phone,
            "identity_birth_date": self.identity_birth_date,
            "identity_address": self.identity_address,
            "identity_city": self.identity_city,
            "identity_state": self.identity_state,
            "stage": self.stage,
            "error": self.error,
            "balance": self.balance,
            "bonus": self.bonus,
            "withdrawn": self.withdrawn,
            "attempts": self.attempts,
            "timestamps": self.timestamps,
        }


@dataclass
class CampaignReport:
    """Full campaign report with P&L summary."""

    campaign_id: str
    config: CampaignConfig
    accounts: list[CampaignAccountStatus] = field(default_factory=list)
    total_extracted: float = 0.0
    total_cost: float = 0.0
    net_profit: float = 0.0
    success_rate: float = 0.0
    duration_s: float = 0.0
    errors: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "config": self.config.to_dict(),
            "accounts": [a.to_dict() for a in self.accounts],
            "total_extracted": self.total_extracted,
            "total_cost": self.total_cost,
            "net_profit": self.net_profit,
            "success_rate": self.success_rate,
            "duration_s": self.duration_s,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# CampaignRunner
# ---------------------------------------------------------------------------

class CampaignRunner:
    """Orchestrates multi-account bonus extraction campaigns.

    Parameters:
        factory: AccountFactory instance (for identity gen + registration)
        engine: Optional wagering strategy engine (any object with .wager())
        orchestrator: Optional withdraw orchestrator (any object with .withdraw())
    """

    def __init__(self, factory: Any, engine: Any = None, orchestrator: Any = None):
        self.factory = factory
        self.engine = engine
        self.orchestrator = orchestrator

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, config: CampaignConfig) -> CampaignReport:
        """Execute a full campaign.

        1. Generate identities via factory
        2. For each account (parallel up to max_parallel):
           register → claim bonus → wager → withdraw
        3. Retry failed accounts (up to max_retries)
        4. Build CampaignReport
        """
        campaign_id = f"camp-{uuid.uuid4().hex[:12]}"
        start_time = time.monotonic()
        log.info("Campaign %s started: %d accounts, platforms=%s, dry_run=%s",
                 campaign_id, config.accounts, config.platforms, config.dry_run)

        # Generate identities
        identities = self.factory.identities.generate_batch(config.accounts)
        log.info("Generated %d identities", len(identities))

        # Build (identity, platform) pairs
        targets: list[tuple[Identity, str]] = []
        for identity in identities:
            for platform in config.platforms:
                targets.append((identity, platform))

        report = CampaignReport(
            campaign_id=campaign_id,
            config=config,
            accounts=[
                CampaignAccountStatus(
                    account_id=f"{identity.email}@{platform}",
                    platform=platform,
                    identity_name=identity.full_name,
                    identity_email=identity.email,
                    identity_cpf=identity.cpf,
                    identity_password=identity.password,
                    identity_phone=identity.phone,
                    identity_birth_date=identity.birth_date,
                    identity_address=identity.address,
                    identity_city=identity.city,
                    identity_state=identity.state,
                    stage=STAGE_PENDING,
                )
                for identity, platform in targets
            ],
        )

        # Execute in parallel
        results = self._parallel_map(
            list(range(len(targets))),
            lambda idx: self._run_single_account(
                targets[idx][0], targets[idx][1], config
            ),
            max_workers=config.max_parallel,
        )

        # Apply results
        for idx, result in enumerate(results):
            if result is not None:
                report.accounts[idx] = result
                if result.stage == STAGE_FAILED:
                    report.errors.append({
                        "account_id": result.account_id,
                        "platform": result.platform,
                        "error": result.error,
                        "attempts": result.attempts,
                    })

        # Retry failed accounts
        if config.retry_failed:
            self._retry_failed(report, config)

        # Compute P&L
        self._compute_pnl(report)

        # Finalize
        report.duration_s = round(time.monotonic() - start_time, 2)
        total = len(report.accounts)
        succeeded = sum(1 for a in report.accounts if a.stage != STAGE_FAILED)
        report.success_rate = round(succeeded / total, 4) if total else 0.0

        log.info(
            "Campaign %s complete: %d/%d succeeded, extracted=%.2f, net=%.2f, duration=%.1fs",
            campaign_id, succeeded, total,
            report.total_extracted, report.net_profit, report.duration_s,
        )
        return report

    # ------------------------------------------------------------------
    # Single account pipeline
    # ------------------------------------------------------------------

    def _run_single_account(
        self,
        identity: Identity,
        platform: str,
        config: CampaignConfig,
    ) -> Optional[CampaignAccountStatus]:
        """Run the full pipeline for a single account.

        Pipeline: register → claim bonus → wager → withdraw
        """
        account_id = f"{identity.email}@{platform}"
        status = CampaignAccountStatus(
            account_id=account_id,
            platform=platform,
            identity_name=identity.full_name,
            identity_email=identity.email,
            identity_cpf=identity.cpf,
            identity_password=identity.password,
            identity_phone=identity.phone,
            identity_birth_date=identity.birth_date,
            identity_address=identity.address,
            identity_city=identity.city,
            identity_state=identity.state,
            stage=STAGE_PENDING,
            attempts=1,
        )
        status.timestamps["started"] = _now_iso()

        if config.dry_run:
            log.info("[DRY RUN] %s @ %s — skipping real execution", identity.email, platform)
            status.stage = STAGE_WAGERED
            status.balance = 100.0
            status.bonus = 50.0
            status.withdrawn = 50.0
            status.timestamps["completed"] = _now_iso()
            return status

        try:
            # Step 1: Register + login
            log.info("  [%s] Registering @ %s...", identity.email, platform)
            reg_result = self.factory.create_account(identity, platform)
            if not reg_result.success:
                status.stage = STAGE_FAILED
                status.error = f"Registration failed: {reg_result.error}"
                status.timestamps["failed"] = _now_iso()
                return status
            status.stage = STAGE_REGISTERED
            status.timestamps["registered"] = _now_iso()
            log.info("  [%s] Registered ✓", identity.email)

            # Step 2: Claim bonus
            if self.engine is not None and hasattr(self.engine, "claim_bonus"):
                claim_result = self.engine.claim_bonus(
                    platform=platform,
                    token=reg_result.token,
                    email=identity.email,
                )
                if isinstance(claim_result, dict):
                    status.bonus = float(claim_result.get("bonus_amount") or 0.0)
                    status.balance = float(claim_result.get("balance") or 0.0)
                status.stage = STAGE_BONUS_CLAIMED
                status.timestamps["bonus_claimed"] = _now_iso()
                log.info("  [%s] Bonus claimed ✓ (%.2f)", identity.email, status.bonus)
            else:
                # No engine — assume bonus auto-granted on registration
                status.stage = STAGE_BONUS_CLAIMED
                status.timestamps["bonus_claimed"] = _now_iso()

            # Step 3: Wager
            if self.engine is not None and hasattr(self.engine, "wager"):
                status.stage = STAGE_WAGERING
                status.timestamps["wagering"] = _now_iso()
                wager_result = self.engine.wager(
                    platform=platform,
                    token=reg_result.token,
                    email=identity.email,
                    method=config.wager_method,
                )
                if isinstance(wager_result, dict):
                    status.balance = float(wager_result.get("balance") or 0.0)
                status.stage = STAGE_WAGERED
                status.timestamps["wagered"] = _now_iso()
                log.info("  [%s] Wagered ✓ (balance=%.2f)", identity.email, status.balance)
            else:
                status.stage = STAGE_WAGERED
                status.timestamps["wagered"] = _now_iso()

            # Step 4: Withdraw
            if self.orchestrator is not None and hasattr(self.orchestrator, "withdraw"):
                withdraw_result = self.orchestrator.withdraw(
                    platform=platform,
                    token=reg_result.token,
                    email=identity.email,
                    amount=status.balance,
                    split=config.withdraw_split,
                )
                if isinstance(withdraw_result, dict):
                    status.withdrawn = float(withdraw_result.get("withdrawn") or 0.0)
                status.stage = STAGE_WITHDRAWN
                status.timestamps["withdrawn"] = _now_iso()
                log.info("  [%s] Withdrawn ✓ (%.2f)", identity.email, status.withdrawn)

        except Exception as exc:
            log.error("  [%s] Pipeline error: %s", identity.email, exc)
            status.stage = STAGE_FAILED
            status.error = str(exc)
            status.timestamps["failed"] = _now_iso()

        status.timestamps["completed"] = _now_iso()
        return status

    # ------------------------------------------------------------------
    # Retry logic
    # ------------------------------------------------------------------

    def _retry_failed(self, report: CampaignReport, config: CampaignConfig) -> None:
        """Retry failed accounts up to config.max_retries times."""
        for attempt in range(1, config.max_retries + 1):
            failed_indices = [
                i for i, a in enumerate(report.accounts)
                if a.stage == STAGE_FAILED
            ]
            if not failed_indices:
                break

            log.info("  Retry pass %d/%d: %d failed accounts",
                     attempt, config.max_retries, len(failed_indices))

            retry_results = self._parallel_map(
                failed_indices,
                lambda idx: self._retry_single(report, idx, config, attempt),
                max_workers=config.max_parallel,
            )

            for idx, result in zip(failed_indices, retry_results):
                if result is not None:
                    report.accounts[idx] = result

            # Prune errors for accounts that succeeded on retry
            failed_ids = {
                a.account_id for a in report.accounts if a.stage == STAGE_FAILED
            }
            report.errors = [e for e in report.errors if e["account_id"] in failed_ids]

    def _retry_single(
        self,
        report: CampaignReport,
        idx: int,
        config: CampaignConfig,
        attempt: int,
    ) -> Optional[CampaignAccountStatus]:
        """Retry a single failed account with a fresh identity."""
        old_status = report.accounts[idx]
        platform = old_status.platform

        # Generate a new identity (fresh email to avoid conflicts)
        new_identity = self.factory.identities.generate()
        new_account_id = f"{new_identity.email}@{platform}"

        log.info("  Retry %d: %s → %s @ %s",
                 attempt, old_status.identity_name, new_identity.email, platform)

        status = self._run_single_account(new_identity, platform, config)
        if status is not None:
            status.attempts = old_status.attempts + 1
            status.account_id = new_account_id
            status.identity_name = new_identity.full_name
        return status

    # ------------------------------------------------------------------
    # Parallel execution
    # ------------------------------------------------------------------

    def _parallel_map(
        self,
        items: list,
        fn: Callable,
        max_workers: int,
    ) -> list:
        """Execute fn(item) for each item in parallel using ThreadPoolExecutor.

        Preserves order of results matching input order.
        """
        if not items:
            return []
        if max_workers <= 1 or len(items) == 1:
            return [fn(item) for item in items]

        results: list = [None] * len(items)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(fn, item): idx
                for idx, item in enumerate(items)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as exc:
                    log.error("  Parallel task %d failed: %s", idx, exc)
                    results[idx] = None
        return results

    # ------------------------------------------------------------------
    # P&L computation
    # ------------------------------------------------------------------

    def _compute_pnl(self, report: CampaignReport) -> None:
        """Compute total extracted, cost, and net profit."""
        total_extracted = 0.0
        total_cost = 0.0

        for account in report.accounts:
            if account.stage in (STAGE_WAGERED, STAGE_WITHDRAWN):
                total_extracted += account.withdrawn if account.withdrawn > 0 else account.balance
            if account.stage != STAGE_FAILED:
                total_cost += 1.0  # ~$1 per account (proxy + infra)

        report.total_extracted = round(total_extracted, 2)
        report.total_cost = round(total_cost, 2)
        report.net_profit = round(total_extracted - total_cost, 2)

    # ------------------------------------------------------------------
    # Progress summary
    # ------------------------------------------------------------------

    def progress(self, report: CampaignReport) -> dict:
        """Build a progress summary dict for dashboard display."""
        total = len(report.accounts)
        if total == 0:
            return {"total": 0, "completed": 0, "failed": 0, "in_progress": 0, "pct": 0.0}

        counts: dict[str, int] = {}
        for a in report.accounts:
            counts[a.stage] = counts.get(a.stage, 0) + 1

        completed = sum(
            counts.get(s, 0)
            for s in (STAGE_REGISTERED, STAGE_BONUS_CLAIMED, STAGE_WAGERING,
                      STAGE_WAGERED, STAGE_WITHDRAWN)
        )
        failed = counts.get(STAGE_FAILED, 0)
        in_progress = total - completed - failed

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "in_progress": max(0, in_progress),
            "pct": round((completed + failed) / total * 100, 1),
            "stages": counts,
            "total_extracted": report.total_extracted,
            "net_profit": report.net_profit,
            "duration_s": report.duration_s,
        }
