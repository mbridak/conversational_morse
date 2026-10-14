"""Main application window."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig, KeyerConfig
from ..keyer import find_winkeyer_port, list_serial_ports
from ..qso import CopyReport, QsoLength, QsoMode
from ..storage import save_config
from .controller import SessionController, SessionState
from .dialogs import StationDialog

SIDETONE_CHOICES: tuple[tuple[str, int], ...] = (
    ("Off", 0),
    ("4000 Hz", 1),
    ("2000 Hz", 2),
    ("1333 Hz", 3),
    ("1000 Hz", 4),
    ("800 Hz", 5),
    ("666 Hz", 6),
    ("571 Hz", 7),
    ("500 Hz", 8),
    ("444 Hz", 9),
    ("400 Hz", 10),
)

SIDETONE_VOLUME_CHOICES: tuple[tuple[str, str], ...] = (
    ("Normal", "normal"),
    ("Low", "low"),
)

SPEAKER_COLOURS: dict[str, str] = {
    "dx": "#1f6feb",
    "user": "#1a7f37",
    "hint": "#8b949e",
    "system": "#9a6700",
}

SPEAKER_LABELS: dict[str, str] = {
    "dx": "DX",
    "user": "YOU",
    "hint": "TIP",
    "system": "SYS",
}


class MainWindow(QMainWindow):
    """The top level window tying the controls to the session controller."""

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self._config = config or AppConfig.default()
        self.controller = SessionController(self._config.keyer, self)
        self.setWindowTitle("Conversational Morse - CW QSO Trainer")
        self.resize(1000, 720)

        self._build_ui()
        self._connect_signals()
        self._refresh_ports()
        self._update_state()

    # -- construction ---------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.addWidget(self._build_connection_group())
        layout.addWidget(self._build_qso_group(), stretch=1)
        layout.addWidget(self._build_input_group())
        self.setCentralWidget(central)

    def _build_connection_group(self) -> QGroupBox:
        group = QGroupBox("WinKeyer")
        outer = QVBoxLayout(group)
        row = QHBoxLayout()

        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setMinimumWidth(220)
        self.refresh_button = QPushButton("Refresh")
        self.simulator_check = QCheckBox("Use simulator")
        self.connect_button = QPushButton("Connect")

        row.addWidget(QLabel("Port:"))
        row.addWidget(self.port_combo, stretch=1)
        row.addWidget(self.refresh_button)
        row.addWidget(self.simulator_check)
        row.addWidget(self.connect_button)
        outer.addLayout(row)

        settings = QHBoxLayout()
        self.wpm_spin = QSpinBox()
        self.wpm_spin.setRange(5, 99)
        self.wpm_spin.setValue(self._config.keyer.wpm)
        self.wpm_spin.setSuffix(" WPM")
        self.sidetone_combo = QComboBox()
        for label, index in SIDETONE_CHOICES:
            self.sidetone_combo.addItem(label, index)
        current = self._config.keyer.sidetone_index
        position = self.sidetone_combo.findData(current)
        if position >= 0:
            self.sidetone_combo.setCurrentIndex(position)

        self.sidetone_volume_combo = QComboBox()
        for label, level in SIDETONE_VOLUME_CHOICES:
            self.sidetone_volume_combo.addItem(label, level)
        volume_position = self.sidetone_volume_combo.findData(
            self._config.keyer.sidetone_volume,
        )
        if volume_position >= 0:
            self.sidetone_volume_combo.setCurrentIndex(volume_position)
        self.sidetone_volume_combo.setToolTip(
            "Sidetone level. WinKeyer 3.1 firmware only offers two levels.",
        )

        settings.addWidget(QLabel("Speed:"))
        settings.addWidget(self.wpm_spin)
        settings.addWidget(QLabel("Sidetone:"))
        settings.addWidget(self.sidetone_combo)
        settings.addWidget(QLabel("Volume:"))
        settings.addWidget(self.sidetone_volume_combo)
        self.station_button = QPushButton("Station setup...")
        settings.addWidget(self.station_button)
        self.require_copy_check = QCheckBox("Require correct copy")
        self.require_copy_check.setChecked(
            self._config.keyer.require_correct_copy,
        )
        self.require_copy_check.setToolTip(
            "Make the DX station ask for a repeat when your over is missing "
            "information or uses the wrong callsign.",
        )
        settings.addWidget(self.require_copy_check)
        settings.addStretch(1)
        outer.addLayout(settings)

        self.status_label = QLabel("Not connected")
        outer.addWidget(self.status_label)
        return group

    def _build_qso_group(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.log_view = QTextBrowser()
        self.log_view.setFont(QFont("Menlo", 12))
        self.log_view.setOpenExternalLinks(False)
        splitter.addWidget(self.log_view)

        controls = QWidget()
        form = QVBoxLayout(controls)

        mode_box = QGroupBox("Start a contact")
        mode_layout = QFormLayout(mode_box)
        self.length_combo = QComboBox()
        for label, length in (
            ("Short (exchange + 73)", QsoLength.SHORT),
            ("Medium (+ rig/antenna/wx)", QsoLength.MEDIUM),
            ("Full rag-chew", QsoLength.FULL),
        ):
            self.length_combo.addItem(label, length)
        self.length_combo.setCurrentIndex(2)
        self.call_cq_button = QPushButton("I will call CQ")
        self.answer_cq_button = QPushButton("Answer the DX station")
        mode_layout.addRow("Length:", self.length_combo)
        mode_layout.addRow(self.call_cq_button)
        mode_layout.addRow(self.answer_cq_button)
        form.addWidget(mode_box)

        turn_box = QGroupBox("Your turn")
        turn_layout = QVBoxLayout(turn_box)
        self.prompt_label = QLabel("Connect to the keyer to begin.")
        self.prompt_label.setWordWrap(True)
        self.send_for_me_button = QPushButton("Send the model answer for me")
        self.end_over_button = QPushButton("End over")
        self.abort_button = QPushButton("Abort QSO")
        turn_layout.addWidget(self.prompt_label)
        turn_layout.addWidget(self.send_for_me_button)
        turn_layout.addWidget(self.end_over_button)
        turn_layout.addWidget(self.abort_button)
        form.addWidget(turn_box)

        self.report_label = QLabel("")
        self.report_label.setWordWrap(True)
        form.addWidget(self.report_label)
        form.addStretch(1)
        splitter.addWidget(controls)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        return splitter

    def _build_input_group(self) -> QGroupBox:
        group = QGroupBox("Paddle input / keyboard fallback")
        layout = QVBoxLayout(group)

        self.paddle_label = QLabel("Received from paddles: -")
        self.paddle_label.setFont(QFont("Menlo", 13))
        layout.addWidget(self.paddle_label)

        row = QHBoxLayout()
        self.typed_input = QLineEdit()
        self.typed_input.setPlaceholderText(
            "No paddles? Type your over here and press Enter (it is keyed for you).",
        )
        layout.addWidget(self.typed_input)
        row.addWidget(QLabel("The typed text is sent through the keyer."))
        row.addStretch(1)
        layout.addLayout(row)
        return group

    # -- signals --------------------------------------------------------
    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self._refresh_ports)
        self.connect_button.clicked.connect(self._toggle_connection)
        self.simulator_check.toggled.connect(lambda _: self._refresh_ports())
        self.wpm_spin.valueChanged.connect(self._on_wpm_changed)
        self.sidetone_volume_combo.currentIndexChanged.connect(
            self._on_sidetone_volume_changed,
        )
        self.station_button.clicked.connect(self._open_station_dialog)
        self.require_copy_check.toggled.connect(self._on_require_copy_toggled)

        self.call_cq_button.clicked.connect(
            lambda: self._start_qso(QsoMode.USER_CALLS_CQ),
        )
        self.answer_cq_button.clicked.connect(
            lambda: self._start_qso(QsoMode.DX_CALLS_CQ),
        )
        self.send_for_me_button.clicked.connect(self.controller.send_for_me)
        self.end_over_button.clicked.connect(self.controller.end_over)
        self.abort_button.clicked.connect(self.controller.abort_session)
        self.typed_input.returnPressed.connect(self._on_typed_submit)

        self.controller.log_message.connect(self._on_log)
        self.controller.status_changed.connect(self.status_label.setText)
        self.controller.connection_changed.connect(self._on_connection_changed)
        self.controller.state_changed.connect(self._update_state)
        self.controller.user_buffer_changed.connect(self._on_user_buffer)
        self.controller.copy_report_ready.connect(self._on_copy_report)
        self.controller.error.connect(self._on_error)
        self.controller.session_finished.connect(self._update_state)

    # -- slots ----------------------------------------------------------
    def _refresh_ports(self) -> None:
        self.port_combo.clear()
        ports = list_serial_ports()
        self.port_combo.addItems(ports)
        guess = find_winkeyer_port()
        if guess:
            self.port_combo.setCurrentText(guess)
        elif ports:
            self.port_combo.setCurrentIndex(0)

    def _toggle_connection(self) -> None:
        if self.controller.is_connected:
            self.controller.disconnect_keyer()
            return
        keyer_config = self._collect_keyer_config()
        self._config.keyer = keyer_config
        save_config(self._config)
        self.controller.configure_settings(keyer_config)
        self.controller.connect_keyer()

    def _open_station_dialog(self) -> None:
        dialog = StationDialog(self._config.station, self)
        if dialog.exec():
            self._config.station = dialog.station()
            save_config(self._config)
            self.status_label.setText(
                f"Station set: {self._config.station.callsign} "
                f"({self._config.station.name})",
            )

    def _collect_keyer_config(self) -> KeyerConfig:
        config = self._config.keyer.model_copy()
        config.port = self.port_combo.currentText().strip() or None
        config.use_simulator = self.simulator_check.isChecked()
        config.wpm = self.wpm_spin.value()
        config.sidetone_index = int(self.sidetone_combo.currentData())
        config.sidetone_volume = str(self.sidetone_volume_combo.currentData())
        config.require_correct_copy = self.require_copy_check.isChecked()
        return config

    def _on_require_copy_toggled(self, checked: bool) -> None:
        self._config.keyer.require_correct_copy = checked
        self.controller.configure_settings(self._config.keyer)
        save_config(self._config)

    def _on_connection_changed(self, connected: bool) -> None:
        self.connect_button.setText("Disconnect" if connected else "Connect")
        self.port_combo.setEnabled(not connected)
        self.simulator_check.setEnabled(not connected)
        self.refresh_button.setEnabled(not connected)

    def _on_wpm_changed(self, value: int) -> None:
        if self.controller.is_connected:
            self.controller.set_wpm(value)

    def _on_sidetone_volume_changed(self) -> None:
        level = str(self.sidetone_volume_combo.currentData())
        self._config.keyer.sidetone_volume = level
        self.controller.set_sidetone_volume(level)
        save_config(self._config)

    def _start_qso(self, mode: QsoMode) -> None:
        length = self.length_combo.currentData()
        self.log_view.clear()
        self.report_label.clear()
        self.controller.start_qso(mode, length, self._config.station)

    def _on_typed_submit(self) -> None:
        text = self.typed_input.text().strip().upper()
        self.typed_input.clear()
        if text:
            self.controller.submit_typed(text)

    def _on_log(self, speaker: str, text: str) -> None:
        colour = SPEAKER_COLOURS.get(speaker, "#c9d1d9")
        label = SPEAKER_LABELS.get(speaker, speaker.upper())
        style = f"color:{colour};"
        if speaker == "hint":
            style += "font-style:italic;"
        self.log_view.append(
            f'<span style="{style}"><b>{label}:</b> {text}</span>',
        )
        bar = self.log_view.verticalScrollBar()
        if bar is not None:
            bar.setValue(bar.maximum())

    def _on_user_buffer(self, text: str) -> None:
        self.paddle_label.setText(f"Received from paddles: {text or '-'}")

    def _on_copy_report(self, report: CopyReport) -> None:
        if report.total == 0 and not report.wrong:
            self.report_label.setText(f"Copy: {report.percent}% - nice sending!")
            return
        problems: list[str] = []
        if report.missing:
            problems.append("missing " + ", ".join(report.missing))
        if report.wrong:
            problems.append("wrong call " + ", ".join(report.wrong))
        detail = "; ".join(problems) if problems else "nothing"
        verdict = "Solid copy!" if report.is_complete else "Check these:"
        self.report_label.setText(f"Copy {report.percent}% - {verdict} {detail}")

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self, "Keyer error", message)

    def _update_state(self) -> None:
        state = self.controller.state
        session_active = (
            self.controller.engine is not None and state is not SessionState.FINISHED
        )
        awaiting = state is SessionState.AWAITING_USER

        self.call_cq_button.setEnabled(
            not session_active and self.controller.is_connected
        )
        self.answer_cq_button.setEnabled(
            not session_active and self.controller.is_connected,
        )
        self.send_for_me_button.setEnabled(awaiting)
        self.end_over_button.setEnabled(awaiting)
        self.abort_button.setEnabled(session_active)

        if state is SessionState.DISCONNECTED:
            self.prompt_label.setText("Connect to the keyer to begin.")
        elif state is SessionState.DX_SENDING:
            self.prompt_label.setText("The DX station is sending. Listen...")
        elif state is SessionState.USER_SENDING:
            self.prompt_label.setText("Keying your over through the WinKeyer...")
        elif state is SessionState.AWAITING_USER:
            turn = (
                self.controller.engine.current_turn if self.controller.engine else None
            )
            if turn is not None:
                self.prompt_label.setText(turn.hint or "Your turn - send your over.")
        elif state is SessionState.FINISHED:
            self.prompt_label.setText("QSO complete. 73!")
        else:
            self.prompt_label.setText("Ready. Start a contact on the right.")
