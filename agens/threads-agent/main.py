"""
Main orchestrator for the Threads automation system.
Runs all agents in sequence or individual agents by name.

Usage:
    python main.py --agent all
    python main.py --agent researcher
    python main.py --agent analyst
    python main.py --agent writer
    python main.py --agent poster
    python main.py --agent fetcher
    python main.py --agent supervisor-status
    python main.py --agent kill-switch-off
"""
import os
os.environ.pop("SSLKEYLOGFILE", None)  # SSL keylog proxy permission error workaround

import argparse
import logging
import sys
from pathlib import Path

# --- Setup logging ---
import config as cfg

# アカウントを先読みしてログファイルのパスを決定
_pre_account = "account1"
for i, arg in enumerate(sys.argv):
    if arg == "--account" and i + 1 < len(sys.argv):
        _pre_account = sys.argv[i + 1]
        break
cfg.switch_account(_pre_account)
cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
cfg.KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format=cfg.LOG_FORMAT,
    datefmt=cfg.LOG_DATE_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(cfg.DATA_DIR / "run.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)

from agents.supervisor import SupervisorAgent, KillSwitchError
from agents.researcher import ResearcherAgent
from agents.analyst import AnalystAgent
from agents.writer import WriterAgent
from agents.poster import PosterAgent
from agents.fetcher import FetcherAgent
from agents.reviewer import ReviewerAgent
from agents.asp_researcher import ASPResearcherAgent


def build_agents():
    supervisor = SupervisorAgent(cfg, cfg.DATA_DIR)
    researcher = ResearcherAgent(cfg, cfg.KNOWLEDGE_DIR, cfg.DATA_DIR)
    analyst = AnalystAgent(cfg, cfg.DATA_DIR)
    writer = WriterAgent(cfg, cfg.KNOWLEDGE_DIR, cfg.DATA_DIR)
    poster = PosterAgent(cfg, cfg.DATA_DIR)
    fetcher = FetcherAgent(cfg, cfg.DATA_DIR)
    reviewer = ReviewerAgent(cfg, cfg.DATA_DIR)
    asp = ASPResearcherAgent(cfg, cfg.KNOWLEDGE_DIR, cfg.DATA_DIR)
    return supervisor, researcher, analyst, writer, poster, fetcher, reviewer, asp


def run_all(supervisor, researcher, analyst, writer, poster, fetcher, mode="auto"):
    """Run the full pipeline in order (without review step)."""
    logger.info(f"=== Starting full pipeline run (mode={mode}) ===")

    supervisor.run_agent("fetcher", fetcher.run)
    supervisor.run_agent("analyst", analyst.run)
    supervisor.run_agent("researcher", researcher.run)
    supervisor.run_agent("writer", lambda: writer.run(batch_size=5, mode=mode))
    supervisor.run_agent("poster", poster.run)

    if mode == "review":
        pending = len([d for d in __import__("json").load(
            open(cfg.DATA_DIR / "drafts.json", encoding="utf-8")
        ) if d.get("status") == "draft"]) if (cfg.DATA_DIR / "drafts.json").exists() else 0
        if pending:
            logger.info(f"=== {pending}件の下書きがレビュー待ちです ===")
            logger.info("=== python main.py --agent review で確認してください ===")

    logger.info("=== Full pipeline run complete ===")


def print_api_status():
    """Print which API keys are available."""
    keys = cfg.check_api_keys()
    print("\n=== API Key Status ===")
    for service, available in keys.items():
        status = "AVAILABLE" if available else "MISSING (mock mode)"
        print(f"  {service.upper()}: {status}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Threads Automation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available agents:
  all              Run full pipeline (fetcher -> analyst -> researcher -> writer -> poster)
  researcher       Collect topics from YouTube (or mock data)
  analyst          Analyze post performance and generate feedback
  writer           Generate posts using Claude API (or mock data)
  poster           Post to Threads API (or mock)
  fetcher          Fetch metrics from Threads API (or mock)
  supervisor-status Show current supervisor state
  kill-switch-off  Deactivate KILL_SWITCH to resume operations
        """
    )
    parser.add_argument(
        "--account",
        default="account1",
        choices=["account1", "account2", "account3"],
        help="Which account to run (default: account1)",
    )
    parser.add_argument(
        "--agent",
        default="all",
        choices=["all", "researcher", "analyst", "writer", "poster", "fetcher",
                 "review", "asp", "supervisor-status", "kill-switch-on", "kill-switch-off"],
        help="Which agent to run (default: all)",
    )
    parser.add_argument(
        "--mode",
        default=None,
        choices=["auto", "review"],
        help=(
            "Operation mode: 'auto' = posts go directly to queue (0%% human), "
            "'review' = posts go to drafts for human approval (5%% human). "
            "Overrides OPERATION_MODE env var."
        ),
    )
    parser.add_argument(
        "--writer-batch",
        type=int,
        default=5,
        help="Number of posts to generate per writer run (default: 5)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force poster to skip time slot and interval checks",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print API key status and exit",
    )

    args = parser.parse_args()

    # アカウント切り替え（モジュール先読みと同じ値を再適用して確実に反映）
    cfg.switch_account(args.account)

    if args.status:
        print_api_status()
        return

    supervisor, researcher, analyst, writer, poster, fetcher, reviewer, asp = build_agents()

    # --mode flag overrides env var
    if args.mode:
        cfg.OPERATION_MODE = args.mode
    effective_mode = getattr(cfg, "OPERATION_MODE", "auto")

    print_api_status()
    print(f"  OPERATION_MODE: {effective_mode.upper()}")
    if effective_mode == "review":
        print("  → 5%人間モード: 投稿は drafts.json に保存されます")
        print("  → レビュー: python main.py --agent review")
    print()

    try:
        if args.agent == "all":
            run_all(supervisor, researcher, analyst, writer, poster, fetcher, mode=effective_mode)

        elif args.agent == "researcher":
            supervisor.check()
            result = researcher.run()
            logger.info(f"Researcher: Added {len(result)} new items to research cache.")

        elif args.agent == "analyst":
            supervisor.check()
            result = analyst.run()
            logger.info(f"Analyst: Feedback written. Analyzed {result.get('total_posts_analyzed', 0)} posts.")

        elif args.agent == "writer":
            supervisor.check()
            result = writer.run(batch_size=args.writer_batch, mode=effective_mode)
            dest = "drafts" if effective_mode == "review" else "queue"
            logger.info(f"Writer: Added {len(result)} posts to {dest}.")

        elif args.agent == "poster":
            supervisor.check()
            result = poster.run(force=args.force)
            logger.info(f"Poster: Posted {len(result)} items.")

        elif args.agent == "fetcher":
            supervisor.check()
            result = fetcher.run()
            logger.info(f"Fetcher: Updated {len(result)} checkpoint(s).")

        elif args.agent == "review":
            supervisor.check()
            result = reviewer.run()
            logger.info(
                f"Review done: approved={result['approved']}, "
                f"skipped={result['skipped']}, edited={result['edited']}"
            )

        elif args.agent == "asp":
            result = asp.run()
            logger.info(f"ASP: {len(result)}件の案件を取得しました。")

        elif args.agent == "supervisor-status":
            print(supervisor.get_status_summary())

        elif args.agent == "kill-switch-on":
            supervisor.activate_kill_switch()
            print("KILL_SWITCH activated. All operations halted.")

        elif args.agent == "kill-switch-off":
            supervisor.deactivate_kill_switch()
            print("KILL_SWITCH deactivated. System is now active.")

    except KillSwitchError as e:
        logger.critical(f"KILL_SWITCH halted execution: {e}")
        print(f"\nERROR: {e}")
        print("To resume, remove data/KILL_SWITCH or run: python main.py --agent kill-switch-off")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
