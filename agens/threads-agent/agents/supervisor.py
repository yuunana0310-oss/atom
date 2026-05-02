"""
Supervisor Agent
- Runs before each agent
- Checks KILL_SWITCH file exists -> halt everything
- Tracks consecutive errors in supervisor_state.json
- If 3+ consecutive errors -> create KILL_SWITCH file and alert
- Logs all agent runs with status
- Checks posting schedule is being followed
"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_ERRORS = 3


class KillSwitchError(SystemExit):
    """Raised when KILL_SWITCH is active."""
    pass


class SupervisorAgent:
    def __init__(self, config, data_dir):
        self.config = config
        self.data_dir = Path(data_dir)
        self.kill_switch_path = self.data_dir / "KILL_SWITCH"
        self.state_path = self.data_dir / "supervisor_state.json"
        self.error_log_path = self.data_dir / "error_log.json"

    def _load_json(self, path, default):
        path = Path(path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return default
        return default

    def _save_json(self, path, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_state(self):
        return self._load_json(self.state_path, {
            "consecutive_errors": 0,
            "last_run": None,
            "agent_runs": [],
            "kill_switch_active": False,
        })

    def _save_state(self, state):
        self._save_json(self.state_path, state)

    def _load_error_log(self):
        return self._load_json(self.error_log_path, [])

    def _save_error_log(self, log):
        self._save_json(self.error_log_path, log)

    def is_kill_switch_active(self):
        """Returns True if the KILL_SWITCH file exists."""
        return self.kill_switch_path.exists()

    def activate_kill_switch(self, reason=""):
        """Creates the KILL_SWITCH file to halt all agents."""
        self.kill_switch_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.kill_switch_path, "w", encoding="utf-8") as f:
            f.write(f"KILL_SWITCH activated at {datetime.now().isoformat()}\nReason: {reason}\n")

        state = self._load_state()
        state["kill_switch_active"] = True
        state["kill_switch_activated_at"] = datetime.now().isoformat()
        state["kill_switch_reason"] = reason
        self._save_state(state)

        logger.critical(f"SupervisorAgent: KILL_SWITCH ACTIVATED. Reason: {reason}")

    def deactivate_kill_switch(self):
        """Removes the KILL_SWITCH file to resume operations."""
        if self.kill_switch_path.exists():
            self.kill_switch_path.unlink()

        state = self._load_state()
        state["kill_switch_active"] = False
        state["consecutive_errors"] = 0
        state["kill_switch_deactivated_at"] = datetime.now().isoformat()
        self._save_state(state)

        logger.info("SupervisorAgent: KILL_SWITCH deactivated. Operations resumed.")

    def check(self):
        """
        Main check - call this before running any agent.
        Raises KillSwitchError if KILL_SWITCH is active.
        """
        if self.is_kill_switch_active():
            logger.critical("SupervisorAgent: KILL_SWITCH is active. Halting all operations.")
            raise KillSwitchError("KILL_SWITCH is active. Remove data/KILL_SWITCH file to resume.")
        logger.debug("SupervisorAgent: Check passed. No KILL_SWITCH.")

    def record_success(self, agent_name):
        """Record a successful agent run and reset consecutive error count."""
        state = self._load_state()
        state["consecutive_errors"] = 0
        state["last_run"] = datetime.now().isoformat()

        # Keep only last 50 run records
        runs = state.get("agent_runs", [])
        runs.append({
            "agent": agent_name,
            "status": "success",
            "timestamp": datetime.now().isoformat(),
        })
        state["agent_runs"] = runs[-50:]
        self._save_state(state)
        logger.info(f"SupervisorAgent: Recorded success for {agent_name}.")

    def record_error(self, agent_name, error_message):
        """
        Record an agent error. Activates KILL_SWITCH if 3 consecutive errors.
        """
        state = self._load_state()
        state["consecutive_errors"] = state.get("consecutive_errors", 0) + 1
        state["last_run"] = datetime.now().isoformat()

        runs = state.get("agent_runs", [])
        runs.append({
            "agent": agent_name,
            "status": "error",
            "error": str(error_message)[:500],
            "timestamp": datetime.now().isoformat(),
        })
        state["agent_runs"] = runs[-50:]
        self._save_state(state)

        # Log to error_log.json
        error_log = self._load_error_log()
        error_log.append({
            "agent": agent_name,
            "error": str(error_message),
            "timestamp": datetime.now().isoformat(),
            "consecutive_count": state["consecutive_errors"],
        })
        # Keep last 200 errors
        self._save_error_log(error_log[-200:])

        logger.error(
            f"SupervisorAgent: Error in {agent_name}: {error_message}. "
            f"Consecutive errors: {state['consecutive_errors']}"
        )

        if state["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
            reason = (
                f"{MAX_CONSECUTIVE_ERRORS} consecutive errors. "
                f"Last agent: {agent_name}. Last error: {error_message}"
            )
            self.activate_kill_switch(reason=reason)
            raise KillSwitchError(
                f"KILL_SWITCH activated after {MAX_CONSECUTIVE_ERRORS} consecutive errors."
            )

    def run_agent(self, agent_name, agent_func, *args, **kwargs):
        """
        Wrapper to run an agent function with error tracking.
        Checks kill switch before running.

        Usage:
            result = supervisor.run_agent("researcher", researcher.run)
        """
        self.check()
        logger.info(f"SupervisorAgent: Starting agent '{agent_name}'")

        try:
            result = agent_func(*args, **kwargs)
            self.record_success(agent_name)
            return result
        except KillSwitchError:
            raise
        except Exception as e:
            self.record_error(agent_name, str(e))
            logger.exception(f"SupervisorAgent: Agent '{agent_name}' raised exception.")
            raise

    def get_status_summary(self):
        """Return a human-readable summary of the supervisor state."""
        state = self._load_state()
        kill_active = self.is_kill_switch_active()

        lines = [
            "=== Supervisor Status ===",
            f"KILL_SWITCH active: {kill_active}",
            f"Consecutive errors: {state.get('consecutive_errors', 0)}",
            f"Last run: {state.get('last_run', 'never')}",
        ]

        recent_runs = state.get("agent_runs", [])[-5:]
        if recent_runs:
            lines.append("Recent runs:")
            for run in reversed(recent_runs):
                status_icon = "OK" if run["status"] == "success" else "ERR"
                lines.append(f"  [{status_icon}] {run['agent']} @ {run['timestamp']}")

        return "\n".join(lines)
