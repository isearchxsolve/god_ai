"""
MainWindow — the primary application window.

Layout
------
┌────────────┬──────────────────────────────────────────┐
│  Sidebar   │  Chat Area (scrollable)                  │
│            │                                          │
│  Profiles  │  [user message]                          │
│  Sessions  │  [assistant message]                      │
│            │  [tool output]                            │
│            │  [reasoning]                              │
│            │                                          │
│            ├──────────────────────────────────────────┤
│            │  Execution Drawer (collapsible)           │
│            ├──────────────────────────────────────────┤
│            │  [Prompt Input]              [Send/Stop]  │
└────────────┴──────────────────────────────────────────┘

The agent runs in a QThread (AgentWorker) and communicates via
AgentSignals.  All UI updates happen in the GUI thread through
queued connections.
"""

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..core.config import ConfigManager
from ..core.signals import AgentSignals
from ..workers.agent_worker import AgentWorker
from .theme import DARK_THEME_QSS
from .widgets.chat_area import ChatAreaWidget
from .widgets.execution_drawer import ExecutionDrawer
from .widgets.profile_dialog import ProfileDialog
from .widgets.sidebar import SidebarWidget


class MainWindow(QMainWindow):
    """Primary application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EmergentSH — Autonomous AI Agent")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        # ── State ──────────────────────────────────────────────────
        self._current_profile: dict | None = None
        self._current_profile_id: str | None = None
        self._project_dir: str = os.getcwd()
        self._worker: AgentWorker | None = None
        self._signals: AgentSignals | None = None
        self._is_running: bool = False
        # When True, the next send resumes a saved session instead of
        # starting fresh. Set by clicking a session in the sidebar.
        self._resume_next: bool = False
        self._resume_goal: str | None = None

        # ── Apply theme ────────────────────────────────────────────
        self.setStyleSheet(DARK_THEME_QSS)

        # ── Build UI ───────────────────────────────────────────────
        self._build_ui()
        self._build_statusbar()

        # ── Auto-select first profile ──────────────────────────────
        self._auto_select_profile()

    # ==================================================================
    # UI construction
    # ==================================================================
    def _build_ui(self) -> None:
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ────────────────────────────────────────────────
        self.sidebar = SidebarWidget()
        self.sidebar.set_working_directory(self._project_dir)
        self.sidebar.profile_selected.connect(self._on_profile_selected)
        self.sidebar.new_profile_requested.connect(self._on_new_profile)
        self.sidebar.clear_context_requested.connect(self._on_clear_context)
        self.sidebar.session_selected.connect(self._on_session_selected)
        self.sidebar.directory_changed.connect(self._on_directory_changed)
        main_layout.addWidget(self.sidebar)

        # ── Right panel (chat + drawer + input) ────────────────────
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Chat area + execution drawer in a resizable vertical splitter.
        # The chat takes most of the space; the drawer can be dragged.
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setHandleWidth(2)
        self._splitter.setChildrenCollapsible(False)

        self.chat_area = ChatAreaWidget()
        self.execution_drawer = ExecutionDrawer()

        self._splitter.addWidget(self.chat_area)
        self._splitter.addWidget(self.execution_drawer)
        # 70% chat / 30% drawer by default
        self._splitter.setStretchFactor(0, 7)
        self._splitter.setStretchFactor(1, 2)
        self._splitter.setSizes([560, 220])

        right_layout.addWidget(self._splitter, stretch=1)

        # Input area
        input_frame = QFrame()
        input_frame.setObjectName("InputFrame")
        input_frame.setFixedHeight(64)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 8, 12, 8)

        self.prompt_input = QPlainTextEdit()
        self.prompt_input.setObjectName("PromptInput")
        self.prompt_input.setPlaceholderText(
            "Enter your goal or prompt…  (Enter to send, Shift+Enter for newline)"
        )
        self.prompt_input.setFixedHeight(44)
        input_layout.addWidget(self.prompt_input, stretch=1)

        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("SendButton")
        self.send_btn.setFixedWidth(90)
        self.send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(self.send_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("StopButton")
        self.stop_btn.setFixedWidth(90)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._on_stop)
        input_layout.addWidget(self.stop_btn)

        right_layout.addWidget(input_frame)

        main_layout.addWidget(right_panel, stretch=1)
        self.setCentralWidget(central)

        # ── Keyboard shortcut: Enter to send ───────────────────────
        send_sc = QShortcut(QKeySequence(Qt.Key.Key_Return), self.prompt_input)
        send_sc.activated.connect(self._on_send)
        newline_sc = QShortcut(
            QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_Return), self.prompt_input
        )
        newline_sc.activated.connect(
            lambda: self.prompt_input.insertPlainText("\n")
        )

    def _build_statusbar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._status_label = QPushButton("Ready")
        self._status_label.setFlat(True)
        self._status_label.setEnabled(False)
        sb.addWidget(self._status_label)

        self._round_label = QPushButton("")
        self._round_label.setFlat(True)
        self._round_label.setEnabled(False)
        sb.addPermanentWidget(self._round_label)

        self._token_label = QPushButton("")
        self._token_label.setFlat(True)
        self._token_label.setEnabled(False)
        sb.addPermanentWidget(self._token_label)

    # ==================================================================
    # Profile management
    # ==================================================================
    def _auto_select_profile(self) -> None:
        profiles = ConfigManager.get_profiles()
        if not profiles:
            self._status_label.setText("No profiles — create one to begin.")
            return
        first_pid = list(profiles.keys())[0]
        self.sidebar.select_profile(first_pid)
        self._on_profile_selected(first_pid)

    def _on_profile_selected(self, pid: str) -> None:
        profile = ConfigManager.get_profile(pid)
        if not profile:
            return
        self._current_profile = profile
        self._current_profile_id = pid
        # Switching profiles invalidates any pending session resume.
        self._resume_next = False
        self._resume_goal = None
        self.sidebar.refresh_sessions(profile.get("name", ""), self._project_dir)
        model_id = "unknown"
        try:
            model_id = profile["models"][profile["default_model"]]["id"]
        except (KeyError, TypeError):
            pass
        self._status_label.setText(
            f"Profile: {profile.get('name', '?')}  ·  Model: {model_id}"
        )

    def _on_directory_changed(self, path: str) -> None:
        """Update the working directory and refresh sessions for it."""
        self._project_dir = path
        self._resume_next = False
        self._resume_goal = None
        if self._current_profile:
            self.sidebar.refresh_sessions(
                self._current_profile.get("name", ""), path
            )
        self._status_label.setText(f"Working directory: {path}")

    def _on_session_selected(self, key: str) -> None:
        """
        Arm a session resume. The session key is "profile::dir"; we switch
        to that profile+dir, then the next Send resumes the saved context.
        """
        if not self._current_profile:
            return
        data = ConfigManager.load_session(
            self._current_profile.get("name", ""), self._project_dir
        )
        # Fall back to looking the key up directly in the sessions map.
        if not data:
            data = ConfigManager.list_sessions().get(key)
        if not data:
            self._status_label.setText("Session not found.")
            return

        self._resume_next = True
        self._resume_goal = data.get("goal")
        goal_preview = (self._resume_goal or "(no goal)")[:60]
        self._status_label.setText(
            f"Session loaded — press Send to resume: {goal_preview}"
        )
        # Surface the resumed goal in the chat so the user sees context.
        self.chat_area.add_message(
            "tool",
            f"📌 Resuming session\nGoal: {self._resume_goal or '(none)'}\n"
            f"{len(data.get('messages', []))} messages restored on next Send.",
        )

    def _on_new_profile(self) -> None:
        dlg = ProfileDialog(parent=self)
        if dlg.exec():
            data = dlg.get_data()
            if not data["key"]:
                QMessageBox.warning(
                    self, "Missing Key", "API key is required."
                )
                return
            pid = ConfigManager.create_profile(
                name=data["name"],
                key=data["key"],
                model_key=data["default_model"],
                rpm=data["rpm"],
                models=data["models"],
            )
            self.sidebar.refresh_profiles()
            self.sidebar.select_profile(pid)
            self._on_profile_selected(pid)

    # ==================================================================
    # Send / Stop
    # ==================================================================
    def _on_send(self) -> None:
        if self._is_running:
            return
        if not self._current_profile:
            QMessageBox.warning(
                self, "No Profile", "Please select or create a profile first."
            )
            return

        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            prompt = "Please proceed."

        # Clear input
        self.prompt_input.clear()

        # Add user message to chat
        self.chat_area.add_message("user", prompt)

        # Set running state
        self._is_running = True
        self.send_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self._status_label.setText("Agent running…")

        # Capture and clear the pending resume flag for this run.
        should_resume = self._resume_next
        self._resume_next = False

        # Create signals + worker
        self._signals = AgentSignals()
        self._connect_signals(self._signals)

        self._worker = AgentWorker(
            profile=self._current_profile,
            project_dir=self._project_dir,
            signals=self._signals,
            prompt=prompt,
            resume=should_resume,
        )
        self._worker.start()

    def _on_stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
            self._status_label.setText("Stopping…")

    def _on_clear_context(self) -> None:
        """Clear the chat and agent context."""
        self.chat_area.clear_messages()
        self.execution_drawer.clear()
        self._status_label.setText("Context cleared.")

    # ==================================================================
    # Signal connections
    # ==================================================================
    def _connect_signals(self, sig: AgentSignals) -> None:
        sig.token_reasoning.connect(self._on_token_reasoning)
        sig.token_content.connect(self._on_token_content)
        sig.response_finished.connect(self._on_response_finished)
        sig.tool_start.connect(self.execution_drawer.on_tool_start)
        sig.tool_executing.connect(self.execution_drawer.on_tool_executing)
        sig.tool_output.connect(self.execution_drawer.on_tool_output)
        sig.tool_result.connect(self._on_tool_result)
        sig.round_started.connect(self._on_round_started)
        sig.agent_finished.connect(self._on_agent_finished)
        sig.status_info.connect(self._on_status_info)
        sig.status_warning.connect(self._on_status_warning)
        sig.error.connect(self._on_error)
        sig.context_compacted.connect(self._on_context_compacted)
        sig.provider_info.connect(self._on_provider_info)
        sig.auto_corrected.connect(self._on_auto_corrected)
        sig.auto_nudged.connect(self._on_auto_nudged)

    # ── Signal handlers ────────────────────────────────────────────
    def _on_token_reasoning(self, text: str) -> None:
        self.chat_area.append_to_last("reasoning", text)

    def _on_token_content(self, text: str) -> None:
        self.chat_area.append_to_last("assistant", text)

    def _on_response_finished(self, content: str) -> None:
        # The streaming already added the content; this is a no-op
        # but could be used for final formatting.
        pass

    def _on_tool_result(self, tool_name: str, result: str) -> None:
        self.execution_drawer.on_tool_result(tool_name, result)
        # Also add a compact tool result bubble in the chat
        preview = result[:500]
        if len(result) > 500:
            preview += f"\n… ({len(result)} chars total)"
        self.chat_area.add_message("tool", f"[{tool_name}]\n{preview}")

    def _on_round_started(self, rnd: int, ctx: int) -> None:
        self._round_label.setText(f"Round {rnd}/100")
        self._token_label.setText(f"~{ctx} tok")

    def _on_agent_finished(self) -> None:
        self._is_running = False
        self.send_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self._status_label.setText("Ready")
        self._worker = None

    def _on_status_info(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _on_status_warning(self, msg: str) -> None:
        self._status_label.setText(f"⚠ {msg}")

    def _on_error(self, msg: str) -> None:
        self._status_label.setText(f"✗ {msg}")
        QMessageBox.critical(self, "Agent Error", msg)

    def _on_context_compacted(self, old_tok: int, new_tok: int) -> None:
        self._status_label.setText(
            f"Context compacted: ~{old_tok} → ~{new_tok} tokens"
        )
        self._token_label.setText(f"~{new_tok} tok")

    def _on_provider_info(self, name: str, model_id: str) -> None:
        self._status_label.setText(f"Streaming from {name} ({model_id})…")

    def _on_auto_corrected(self, msg: str) -> None:
        self.chat_area.add_message("tool", f"⚠ Auto-Correction: {msg}")

    def _on_auto_nudged(self, msg: str) -> None:
        self.chat_area.add_message("tool", f"⚠ Auto-Nudge: {msg}")

    # ==================================================================
    # Cleanup
    # ==================================================================
    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.wait(5000)
        event.accept()
