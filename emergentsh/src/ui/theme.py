"""
DARK_THEME — QSS stylesheet for a modern dark interface.

Colour palette inspired by Tokyo Night:
  bg          #1a1b26    panel       #16161e / #1f2335
  border      #3b4261    accent      #7aa2f7
  text        #c0caf5    muted       #565f89
  ok/green    #9ece6a    warn/yellow #e0af68
  err/red     #f7768e    think/purple #bb9af7
"""

DARK_THEME_QSS = """
/* ── Global ──────────────────────────────────────────────────────── */
QWidget {
    background-color: #1a1b26;
    color: #c0caf5;
    font-family: "Segoe UI", "Cascadia Code", "Consolas", sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #1a1b26;
}

/* ── Scrollbars ──────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: #16161e;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3b4261;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #565f89;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #16161e;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #3b4261;
    min-width: 30px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #565f89;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Sidebar ─────────────────────────────────────────────────────── */
#Sidebar {
    background-color: #16161e;
    border-right: 1px solid #3b4261;
}
#Sidebar QLabel#SidebarTitle {
    color: #7aa2f7;
    font-size: 15px;
    font-weight: bold;
    padding: 8px 12px 4px 12px;
}
#Sidebar QLabel#SectionLabel {
    color: #565f89;
    font-size: 11px;
    font-weight: bold;
    padding: 8px 12px 2px 12px;
    text-transform: uppercase;
}

/* ── Profile / Session list ──────────────────────────────────────── */
QListWidget {
    background-color: #16161e;
    border: none;
    outline: none;
}
QListWidget::item {
    padding: 6px 12px;
    border-radius: 4px;
    color: #a9b1d6;
}
QListWidget::item:hover {
    background-color: #1f2335;
}
QListWidget::item:selected {
    background-color: #2d3f5f;
    color: #7aa2f7;
    font-weight: bold;
}

/* ── Chat area ───────────────────────────────────────────────────── */
#ChatScroll {
    background-color: #1a1b26;
    border: none;
}
#ChatContainer {
    background-color: #1a1b26;
}

/* Message bubbles */
QFrame#UserBubble {
    background-color: #1f2335;
    border: 1px solid #3b4261;
    border-radius: 8px;
}
QFrame#AssistantBubble {
    background-color: #16161e;
    border: 1px solid #3b4261;
    border-radius: 8px;
}
QFrame#ToolBubble {
    background-color: #1a1b26;
    border: 1px dashed #3b4261;
    border-radius: 6px;
}
QFrame#ReasoningBubble {
    background-color: #1a1b26;
    border-left: 3px solid #bb9af7;
    border-radius: 0px;
}
QLabel#RoleLabel {
    font-size: 11px;
    font-weight: bold;
    padding: 2px 0;
}
QLabel#RoleUser { color: #7aa2f7; }
QLabel#RoleAssistant { color: #9ece6a; }
QLabel#RoleTool { color: #e0af68; }
QLabel#RoleReasoning { color: #bb9af7; }
QLabel#ContentLabel {
    color: #c0caf5;
}
QLabel#ReasoningContent {
    color: #bb9af7;
    font-style: italic;
}

/* ── Input area ──────────────────────────────────────────────────── */
#InputFrame {
    background-color: #16161e;
    border-top: 1px solid #3b4261;
}
QPlainTextEdit#PromptInput {
    background-color: #1f2335;
    border: 1px solid #3b4261;
    border-radius: 8px;
    padding: 8px;
    color: #c0caf5;
    font-size: 14px;
    selection-background-color: #2d3f5f;
}
QPlainTextEdit#PromptInput:focus {
    border: 1px solid #7aa2f7;
}

/* ── Buttons ─────────────────────────────────────────────────────── */
QPushButton {
    background-color: #1f2335;
    border: 1px solid #3b4261;
    border-radius: 6px;
    padding: 6px 16px;
    color: #c0caf5;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #2d3f5f;
    border-color: #7aa2f7;
}
QPushButton:pressed {
    background-color: #7aa2f7;
    color: #1a1b26;
}
QPushButton:disabled {
    background-color: #16161e;
    color: #565f89;
    border-color: #2a2e3f;
}
QPushButton#SendButton {
    background-color: #7aa2f7;
    border: none;
    color: #1a1b26;
    font-weight: bold;
    border-radius: 6px;
    padding: 8px 24px;
}
QPushButton#SendButton:hover {
    background-color: #89b0ff;
}
QPushButton#SendButton:disabled {
    background-color: #2a2e3f;
    color: #565f89;
}
QPushButton#StopButton {
    background-color: #f7768e;
    border: none;
    color: #1a1b26;
    font-weight: bold;
    border-radius: 6px;
    padding: 8px 24px;
}
QPushButton#StopButton:hover {
    background-color: #ff8fa3;
}

/* ── Execution Drawer ────────────────────────────────────────────── */
#ExecutionDrawer {
    background-color: #16161e;
    border-top: 1px solid #3b4261;
}
#ExecutionDrawer QLabel#DrawerTitle {
    color: #e0af68;
    font-size: 13px;
    font-weight: bold;
    padding: 6px 12px;
}
QPlainTextEdit#TerminalOutput {
    background-color: #0f0f14;
    border: none;
    color: #9ece6a;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 4px 8px;
    selection-background-color: #2d3f5f;
}

/* ── Status bar ──────────────────────────────────────────────────── */
QStatusBar {
    background-color: #16161e;
    border-top: 1px solid #3b4261;
    color: #565f89;
    font-size: 11px;
}
QStatusBar QLabel {
    color: #565f89;
    padding: 0 8px;
}

/* ── Splitter ────────────────────────────────────────────────────── */
QSplitter::handle {
    background-color: #3b4261;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}

/* ── Tooltips ────────────────────────────────────────────────────── */
QToolTip {
    background-color: #1f2335;
    color: #c0caf5;
    border: 1px solid #3b4261;
    border-radius: 4px;
    padding: 4px 8px;
}

/* ── Dialog ───────────────────────────────────────────────────────── */
QDialog {
    background-color: #1a1b26;
}
QLineEdit, QSpinBox, QComboBox {
    background-color: #1f2335;
    border: 1px solid #3b4261;
    border-radius: 4px;
    padding: 6px 8px;
    color: #c0caf5;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #7aa2f7;
}
QGroupBox {
    border: 1px solid #3b4261;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    color: #7aa2f7;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}
"""
