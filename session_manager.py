"""
session_manager.py — MOBBO Session & Folder Hierarchy Manager

Implements the canonical folder structure:

Mobbo_data/
└── <patient_id>/
    └── session_<DDMMYYYY_HHMMSS>/           ← ONE per login
        ├── Assessment/
        │   ├── Pose1/                        ← increments on board reset
        │   │   ├── Board_Data/
        │   │   │   └── Board_Poses.json
        │   │   ├── CoP_Data/
        │   │   │   ├── trial1/
        │   │   │   │   └── data_<ip>.csv
        │   │   │   └── trial2/
        │   │   │       └── data_<ip>.csv
        │   │   └── Foot_Data/
        │   │       ├── trial1/
        │   │       └── trial2/
        │   └── Pose2/
        │       └── ...
        └── Games/
            └── <game_name>/
                ├── Pose1/
                │   ├── Board_Data/
                │   ├── CoP_Data/
                │   │   └── trial1/
                │   └── Foot_Data/
                └── Pose2/

Usage:
    from session_manager import SessionManager

    mgr = SessionManager()
    mgr.start_session("22121")          # called on Godot login

    # Each board detection / reset:
    mgr.next_pose()

    # Each Start Recording (Assessment):
    trial_path = mgr.next_trial("Assessment")

    # Each Start Recording (Game):
    trial_path = mgr.next_trial("Games", game_name="BallBalance")

    # Board_Poses.json path for current pose:
    json_path = mgr.board_data_path()
"""

import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Base data directory (same drive as project) ───────────────────────────────
_BASE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "Mobbo_data"
)


class SessionManager:
    """
    Single source of truth for the MOBBO data folder hierarchy.

    One instance is created when the patient logs in and lives for the
    entire Python session.  All components (DataLogging, COP_wifi_data,
    board_pose_json_recorder) ask this manager for their paths.
    """

    def __init__(self, base_dir: str = _BASE_DIR):
        self._base_dir     = base_dir
        self._patient_id   = None
        self._session_path = None   # Mobbo_data/<patient>/session_<ts>/
        self._pose_index   = 0      # 1-based: Pose1, Pose2, …
        self._trial_counts = {}     # { "Assessment/Pose1": 2, "Games/BallBalance/Pose1": 1, … }

    # ─────────────────────────────────────────────────────────────────────────
    # Session lifecycle
    # ─────────────────────────────────────────────────────────────────────────

    def start_session(self, patient_id: str) -> str:
        """
        Create the session folder for this patient.
        Must be called ONCE when the patient logs in.
        Subsequent calls are ignored if the same patient is already active.

        Returns the session folder path.
        """
        patient_id = patient_id.strip()

        # If same patient already has an active session, reuse it
        if self._patient_id == patient_id and self._session_path:
            logger.info(f"ℹ️  Session already active for '{patient_id}': {self._session_path}")
            return self._session_path

        self._patient_id   = patient_id
        self._pose_index   = 0
        self._trial_counts = {}

        timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
        session_name = f"session_{timestamp}"

        self._session_path = os.path.join(
            self._base_dir, patient_id, session_name
        )
        os.makedirs(self._session_path, exist_ok=True)

        # Pre-create top-level Assessment and Games folders
        os.makedirs(os.path.join(self._session_path, "Assessment"), exist_ok=True)
        os.makedirs(os.path.join(self._session_path, "Games"), exist_ok=True)

        print(f"✅ Session started: {self._session_path}")
        logger.info(f"✅ Session folder created: {self._session_path}")
        return self._session_path

    def end_session(self):
        """Reset internal state (called on logout / app quit)."""
        self._patient_id   = None
        self._session_path = None
        self._pose_index   = 0
        self._trial_counts = {}
        logger.info("Session ended")

    # ─────────────────────────────────────────────────────────────────────────
    # Pose management  (call on board reset)
    # ─────────────────────────────────────────────────────────────────────────

    def next_pose(self) -> int:
        """
        Advance to the next pose index (Pose1 → Pose2 → …).
        Creates all required sub-folders for both Assessment and Games.
        Returns the new pose number.
        """
        self._require_session()
        self._pose_index += 1

        # Pre-create Board_Data folders for Assessment and Games
        for mode in ["Assessment", "Games"]:
            board_dir = self._pose_dir(mode, pose=self._pose_index)
            bd = os.path.join(board_dir, "Board_Data")
            os.makedirs(bd, exist_ok=True)
            logger.debug(f"Created: {bd}")

        print(f"📐 Now on Pose{self._pose_index}")
        logger.info(f"Pose advanced to Pose{self._pose_index}")
        return self._pose_index

    @property
    def pose_number(self) -> int:
        return self._pose_index

    # ─────────────────────────────────────────────────────────────────────────
    # Trial management  (call on Start Recording)
    # ─────────────────────────────────────────────────────────────────────────

    def next_trial(self, mode: str = "Assessment",
                   game_name: Optional[str] = None) -> str:
        """
        Create and return the path for the next trial folder.

        Args:
            mode      : "Assessment" or "Games"
            game_name : Required when mode == "Games" (e.g. "BallBalance")

        Returns:
            Absolute path to the new trial folder,
            e.g. …/Assessment/Pose1/CoP_Data/trial1/
            Callers should save their per-sensor CSVs INSIDE this folder.

        Note: This creates the trial folder for CoP_Data.
              The corresponding Foot_Data trial folder is also created.
        """
        self._require_session()

        key = self._trial_key(mode, game_name)
        trial_num = self._trial_counts.get(key, 0) + 1
        self._trial_counts[key] = trial_num
        trial_name = f"trial{trial_num}"

        pose_dir = self._pose_dir(mode, game_name=game_name)

        # Create CoP_Data/trialN  and  Foot_Data/trialN
        cop_trial  = os.path.join(pose_dir, "CoP_Data",  trial_name)
        foot_trial = os.path.join(pose_dir, "Foot_Data", trial_name)
        os.makedirs(cop_trial,  exist_ok=True)
        os.makedirs(foot_trial, exist_ok=True)

        print(f"▶️  Trial {trial_num} started → {cop_trial}")
        logger.info(f"Trial folder created: {cop_trial}")
        return cop_trial   # primary path returned; foot path is sibling /Foot_Data/trialN

    def current_trial_cop_path(self, mode: str = "Assessment",
                               game_name: Optional[str] = None) -> Optional[str]:
        """Return the CoP_Data/trialN folder for the current (latest) trial, or None."""
        self._require_session()
        key = self._trial_key(mode, game_name)
        trial_num = self._trial_counts.get(key, 0)
        if trial_num == 0:
            return None
        return os.path.join(
            self._pose_dir(mode, game_name=game_name),
            "CoP_Data", f"trial{trial_num}"
        )

    def current_trial_foot_path(self, mode: str = "Assessment",
                                game_name: Optional[str] = None) -> Optional[str]:
        """Return the Foot_Data/trialN folder for the current (latest) trial, or None."""
        cop = self.current_trial_cop_path(mode, game_name)
        if cop is None:
            return None
        # Replace CoP_Data with Foot_Data in the path
        return cop.replace(
            os.sep + "CoP_Data" + os.sep,
            os.sep + "Foot_Data" + os.sep
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Path helpers
    # ─────────────────────────────────────────────────────────────────────────

    def board_data_path(self, mode: str = "Assessment",
                        game_name: Optional[str] = None) -> str:
        """
        Return the Board_Data folder for the current pose.
        This is where Board_Poses.json lives.
        """
        self._require_session()
        return os.path.join(self._pose_dir(mode, game_name=game_name), "Board_Data")

    def board_poses_json_path(self, mode: str = "Assessment",
                              game_name: Optional[str] = None) -> str:
        """Full path to Board_Poses.json for current pose."""
        return os.path.join(self.board_data_path(mode, game_name), "Board_Poses.json")

    @property
    def session_path(self) -> Optional[str]:
        return self._session_path

    @property
    def patient_id(self) -> Optional[str]:
        return self._patient_id

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _require_session(self):
        if not self._session_path:
            raise RuntimeError("No active session. Call start_session(patient_id) first.")

    def _pose_dir(self, mode: str, game_name: Optional[str] = None,
                  pose: Optional[int] = None) -> str:
        """
        Build the path to the PoseN directory.

        Assessment:  session/Assessment/PoseN/
        Games:       session/Games/<game_name>/PoseN/
        """
        p = pose if pose is not None else self._pose_index
        pose_name = f"Pose{p}"

        if mode == "Assessment":
            return os.path.join(self._session_path, "Assessment", pose_name)
        elif mode == "Games":
            if not game_name:
                game_name = "UnknownGame"
            return os.path.join(self._session_path, "Games", game_name, pose_name)
        else:
            raise ValueError(f"Unknown mode '{mode}'. Use 'Assessment' or 'Games'.")

    def _trial_key(self, mode: str, game_name: Optional[str] = None) -> str:
        p = self._pose_index
        if mode == "Assessment":
            return f"Assessment/Pose{p}"
        else:
            return f"Games/{game_name or 'UnknownGame'}/Pose{p}"

    # ─────────────────────────────────────────────────────────────────────────
    # Debug / status
    # ─────────────────────────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "patient_id":   self._patient_id,
            "session_path": self._session_path,
            "pose":         self._pose_index,
            "trial_counts": dict(self._trial_counts),
        }

    def __repr__(self):
        return (f"SessionManager(patient='{self._patient_id}', "
                f"pose={self._pose_index}, session='{self._session_path}')")


# ── Global singleton ──────────────────────────────────────────────────────────
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Return the global SessionManager instance, creating it if needed."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def reset_session_manager():
    """Reset the global instance (for testing or re-login)."""
    global _session_manager
    _session_manager = None