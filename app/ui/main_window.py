# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.8
# Date: 5/20/2026
# Purpose: Main application graphical user interface constructed via PySide6 window controls.

import logging
from pathlib import Path
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit,
    QProgressBar, QCheckBox, QFrame, QFileDialog, QMessageBox, QStatusBar
)
from app.core.models import FileFormat, ConversionPlan, HashResult, PlannerError
from app.core.detector import FormatDetector
from app.core.conversion_planner import ConversionPlanner
from app.core.conversion_service import ConversionService
from app.ui.dialogs import DialogHelper
from app.workers.conversion_worker import ConversionWorker
from app.workers.hash_worker import HashWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """The central user interface for B.R.I.D.G.E.
    Acts as both the UI layer and the controller — spawning workers, binding their
    signals to UI slots, and enforcing pre-flight validation before any execution.
    """

    def __init__(self):
        super().__init__()
        logger.info("Initializing MainWindow.")

        self.setWindowTitle("B.R.I.D.G.E. - Byte-level Routing for Image Data Graphical Extension")
        self.resize(1000, 750)
        self.setMinimumSize(850, 650)

        # Application state
        self.detected_format: FileFormat = FileFormat.UNKNOWN
        self.current_plan: ConversionPlan | None = None
        self._active_worker: ConversionWorker | None = None   # live QThread handle
        self._thread_pool = QThreadPool.globalInstance()
        self._hash_workers_pending: int = 0   # count of hash workers still running

        # Build UI
        self._apply_theme()
        self._init_menu_bar()
        self._init_ui()
        self._init_status_bar()

        logger.info("MainWindow fully loaded.")

    # =========================================================================
    # Theme & Layout Construction
    # =========================================================================

    def _apply_theme(self):
        """Applies a premium, high-contrast dark-mode cyber-forensics stylesheet."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f172a;
            }
            QWidget {
                color: #f1f5f9;
                font-family: "Segoe UI", -apple-system, sans-serif;
                font-size: 13px;
            }
            QLabel {
                font-weight: 500;
            }
            QFrame#container {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            QFrame#divider {
                background-color: #334155;
                max-height: 1px;
            }
            QLineEdit {
                background-color: #0f172a;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 6px 10px;
                color: #f8fafc;
            }
            QLineEdit:focus {
                border: 1px solid #06b6d4;
            }
            QLineEdit:read-only {
                background-color: #1e293b;
                color: #94a3b8;
            }
            QPushButton {
                background-color: #0284c7;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: 600;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton:pressed {
                background-color: #075985;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
            QPushButton#actionRun {
                background-color: #10b981;
            }
            QPushButton#actionRun:hover {
                background-color: #059669;
            }
            QPushButton#actionRun:pressed {
                background-color: #047857;
            }
            QPushButton#actionCancel {
                background-color: #ef4444;
            }
            QPushButton#actionCancel:hover {
                background-color: #dc2626;
            }
            QPushButton#actionCancel:pressed {
                background-color: #b91c1c;
            }
            QPushButton#actionClear {
                background-color: #475569;
            }
            QPushButton#actionClear:hover {
                background-color: #334155;
            }
            QComboBox {
                background-color: #0f172a;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 5px 10px;
                color: #f8fafc;
            }
            QComboBox:focus {
                border: 1px solid #06b6d4;
            }
            QTextEdit {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px;
                font-family: "Consolas", "JetBrains Mono", monospace;
                font-size: 12px;
                color: #e2e8f0;
            }
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
                text-align: center;
                font-weight: bold;
                color: #ffffff;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #06b6d4;
                border-radius: 3px;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #475569;
                border-radius: 3px;
                background-color: #0f172a;
            }
            QCheckBox::indicator:checked {
                background-color: #06b6d4;
                border: 1px solid #06b6d4;
            }
            QStatusBar {
                background-color: #0f172a;
                border-top: 1px solid #334155;
                color: #94a3b8;
            }
        """)

    def _init_menu_bar(self):
        """Builds navigation header controls."""
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        help_menu = menu_bar.addMenu("&Help")
        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self._show_about_dialog)

    def _init_ui(self):
        """Constructs layout containment tree and connects all button triggers."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # --- Header ---
        header_layout = QHBoxLayout()
        branding_layout = QVBoxLayout()
        branding_layout.setSpacing(2)

        title_label = QLabel("B.R.I.D.G.E.")
        title_font = title_label.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #06b6d4;")
        branding_layout.addWidget(title_label)

        subtitle_label = QLabel("Byte-level Routing for Image Data Graphical Extension")
        subtitle_font = subtitle_label.font()
        subtitle_font.setPointSize(10)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("color: #94a3b8;")
        branding_layout.addWidget(subtitle_label)

        header_layout.addLayout(branding_layout)
        header_layout.addStretch()

        self.chk_dry_run = QCheckBox("Dry Run Mode")
        self.chk_dry_run.setToolTip("Print exact CLI commands without executing them.")
        self.chk_dry_run.stateChanged.connect(self._on_dry_run_toggled)
        header_layout.addWidget(self.chk_dry_run)
        main_layout.addLayout(header_layout)

        div = QFrame()
        div.setObjectName("divider")
        main_layout.addWidget(div)

        # --- Source Selection ---
        source_frame = QFrame()
        source_frame.setObjectName("container")
        source_layout = QVBoxLayout(source_frame)
        source_layout.setContentsMargins(12, 12, 12, 12)

        source_title_row = QHBoxLayout()
        source_title_row.addWidget(QLabel("<b>Evidence Source File Selection:</b>"))

        self.lbl_detected_badge = QLabel("DETECTED: UNKNOWN")
        self.lbl_detected_badge.setStyleSheet(
            "background-color: #475569; color: #ffffff; border-radius: 4px; "
            "padding: 3px 8px; font-size: 11px; font-weight: bold;"
        )
        source_title_row.addWidget(self.lbl_detected_badge)
        source_title_row.addStretch()
        source_layout.addLayout(source_title_row)

        source_input_row = QHBoxLayout()
        self.txt_source_path = QLineEdit()
        self.txt_source_path.setReadOnly(True)
        self.txt_source_path.setPlaceholderText(
            "Select raw disk image, virtual partition, or E01 file..."
        )
        source_input_row.addWidget(self.txt_source_path)

        self.btn_browse_source = QPushButton("Browse Source...")
        self.btn_browse_source.clicked.connect(self._on_browse_source)
        source_input_row.addWidget(self.btn_browse_source)
        source_layout.addLayout(source_input_row)
        main_layout.addWidget(source_frame)

        # --- Middle: Configuration + Plan Preview ---
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(12)

        config_frame = QFrame()
        config_frame.setObjectName("container")
        config_layout = QVBoxLayout(config_frame)
        config_layout.setContentsMargins(12, 12, 12, 12)
        config_layout.addWidget(QLabel("<b>Target Configurations:</b>"))

        form_grid = QGridLayout()
        form_grid.setSpacing(10)

        form_grid.addWidget(QLabel("Target Format:"), 0, 0)
        self.cmb_target_format = QComboBox()
        self.cmb_target_format.currentIndexChanged.connect(self._on_target_format_changed)
        form_grid.addWidget(self.cmb_target_format, 0, 1)

        form_grid.addWidget(QLabel("Destination Dir:"), 1, 0)
        dest_row = QHBoxLayout()
        self.txt_dest_path = QLineEdit()
        self.txt_dest_path.textChanged.connect(self._on_inputs_updated)
        dest_row.addWidget(self.txt_dest_path)
        self.btn_browse_dest = QPushButton("Browse...")
        self.btn_browse_dest.clicked.connect(self._on_browse_dest)
        dest_row.addWidget(self.btn_browse_dest)
        form_grid.addLayout(dest_row, 1, 1)

        form_grid.addWidget(QLabel("Output Filename:"), 2, 0)
        self.txt_output_name = QLineEdit()
        self.txt_output_name.textChanged.connect(self._on_inputs_updated)
        form_grid.addWidget(self.txt_output_name, 2, 1)
        config_layout.addLayout(form_grid)

        self.lbl_warning_badge = QLabel("⚠️  Warning: Selected path is Experimental.")
        self.lbl_warning_badge.setStyleSheet(
            "background-color: #78350f; border: 1px solid #d97706; color: #fef3c7; "
            "border-radius: 4px; padding: 6px; font-size: 11px;"
        )
        self.lbl_warning_badge.setVisible(False)
        config_layout.addWidget(self.lbl_warning_badge)
        config_layout.addStretch()
        middle_layout.addWidget(config_frame, 1)

        preview_frame = QFrame()
        preview_frame.setObjectName("container")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.addWidget(QLabel("<b>Scheduled Conversion Plan:</b>"))
        self.txt_plan_preview = QTextEdit()
        self.txt_plan_preview.setReadOnly(True)
        self.txt_plan_preview.setPlaceholderText(
            "The execution plan will appear here after selecting source and target..."
        )
        preview_layout.addWidget(self.txt_plan_preview)
        middle_layout.addWidget(preview_frame, 1)
        main_layout.addLayout(middle_layout)

        # --- Hash Panel ---
        hash_frame = QFrame()
        hash_frame.setObjectName("container")
        hash_layout = QVBoxLayout(hash_frame)
        hash_layout.setContentsMargins(12, 12, 12, 12)
        hash_layout.addWidget(
            QLabel("<b>Evidence Cryptographic Checksums (Chain of Custody Verification):</b>")
        )
        hash_grid = QGridLayout()
        hash_grid.setSpacing(6)

        hash_grid.addWidget(QLabel("Source MD5:"), 0, 0)
        self.txt_hash_src_md5 = QLineEdit()
        self.txt_hash_src_md5.setReadOnly(True)
        hash_grid.addWidget(self.txt_hash_src_md5, 0, 1)

        hash_grid.addWidget(QLabel("Source SHA-256:"), 0, 2)
        self.txt_hash_src_sha256 = QLineEdit()
        self.txt_hash_src_sha256.setReadOnly(True)
        hash_grid.addWidget(self.txt_hash_src_sha256, 0, 3)

        hash_grid.addWidget(QLabel("Output MD5:"), 1, 0)
        self.txt_hash_out_md5 = QLineEdit()
        self.txt_hash_out_md5.setReadOnly(True)
        hash_grid.addWidget(self.txt_hash_out_md5, 1, 1)

        hash_grid.addWidget(QLabel("Output SHA-256:"), 1, 2)
        self.txt_hash_out_sha256 = QLineEdit()
        self.txt_hash_out_sha256.setReadOnly(True)
        hash_grid.addWidget(self.txt_hash_out_sha256, 1, 3)

        hash_layout.addLayout(hash_grid)

        # Hash verification progress (hidden until hashing is active)
        hash_progress_row = QHBoxLayout()
        self.lbl_hash_status = QLabel("Verifying integrity...")
        self.lbl_hash_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        hash_progress_row.addWidget(self.lbl_hash_status)
        self.hash_progress_bar = QProgressBar()
        self.hash_progress_bar.setValue(0)
        self.hash_progress_bar.setFormat("Hash %p%")
        self.hash_progress_bar.setFixedHeight(14)
        self.hash_progress_bar.setStyleSheet(
            "QProgressBar { font-size: 10px; } "
            "QProgressBar::chunk { background-color: #8b5cf6; }"
        )
        hash_progress_row.addWidget(self.hash_progress_bar, 1)
        hash_layout.addLayout(hash_progress_row)

        # Container for the whole hash row — hidden until verification runs
        self._hash_progress_row_widget = QWidget()
        self._hash_progress_row_widget.setLayout(hash_progress_row)
        self._hash_progress_row_widget.setVisible(False)
        hash_layout.addWidget(self._hash_progress_row_widget)

        main_layout.addWidget(hash_frame)

        # --- Log Panel + Progress ---
        log_frame = QFrame()
        log_frame.setObjectName("container")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(12, 12, 12, 12)
        log_layout.addWidget(QLabel("<b>Execution Logs & Diagnostic Output:</b>"))
        self.txt_log_pane = QTextEdit()
        self.txt_log_pane.setReadOnly(True)
        self.txt_log_pane.setPlaceholderText("Console logs stream here during processing...")
        log_layout.addWidget(self.txt_log_pane)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        log_layout.addWidget(self.progress_bar)
        main_layout.addWidget(log_frame, 1)

        # --- Action Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_run = QPushButton("Run Conversion")
        self.btn_run.setObjectName("actionRun")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._on_run_clicked)
        btn_layout.addWidget(self.btn_run)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("actionCancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self.btn_cancel)

        btn_layout.addStretch()

        self.btn_clear = QPushButton("Clear Dashboard")
        self.btn_clear.setObjectName("actionClear")
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        btn_layout.addWidget(self.btn_clear)
        main_layout.addLayout(btn_layout)

    def _init_status_bar(self):
        """Establishes status alerts at window base."""
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("System Ready")

    # =========================================================================
    # File Selection & Format Detection
    # =========================================================================

    def _on_browse_source(self):
        """Triggers QFileDialog to pick target forensic source files."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Forensic/Virtual Disk Image Source",
            "",
            "All Supported Images (*.e01 *.ex01 *.dmg *.dd *.raw *.img *.vmdk *.vhd *.vhdx *.qcow2);;"
            "EnCase Evidence Files (*.e01 *.ex01);;"
            "Raw Disk Images (*.dd *.raw *.img);;"
            "Virtual Machine Hard Disks (*.vmdk *.vhd *.vhdx *.qcow2);;"
            "Apple DMG Files (*.dmg);;"
            "All Files (*)"
        )
        if not filepath:
            return

        logger.info(f"Source file selected: {filepath}")
        self.txt_source_path.setText(filepath)
        self._slot_append_log(
            f"<font color='#06b6d4'>[SYSTEM]: Selected source file: {filepath}</font>"
        )

        detected = FormatDetector.detect_format(filepath)
        self.detected_format = detected.format

        self.lbl_detected_badge.setText(f"DETECTED: {detected.format.value}")
        if detected.format == FileFormat.UNKNOWN:
            self.lbl_detected_badge.setStyleSheet(
                "background-color: #ef4444; color: #ffffff; border-radius: 4px; "
                "padding: 3px 8px; font-weight: bold;"
            )
            self._slot_append_log(
                f"<font color='orange'>[WARNING]: Format unrecognised "
                f"(Method: {detected.method.value}). Conversion unavailable.</font>"
            )
        else:
            self.lbl_detected_badge.setStyleSheet(
                "background-color: #10b981; color: #ffffff; border-radius: 4px; "
                "padding: 3px 8px; font-weight: bold;"
            )
            self._slot_append_log(
                f"<font color='#10b981'>[SYSTEM]: Format identified as "
                f"<b>{detected.format.value}</b> "
                f"(Method: {detected.method.value}, Confidence: {detected.confidence})</font>"
            )

        self._populate_targets(detected.format)
        self.status_bar.showMessage(
            f"Source format detected: {detected.format.value} "
            f"(Method: {detected.method.value})"
        )

    def _populate_targets(self, source_format: FileFormat):
        """Filters dynamic compatible options depending on selected input type."""
        self.cmb_target_format.clear()

        if source_format == FileFormat.UNKNOWN:
            self._update_plan_display(None)
            self._on_inputs_updated()
            return

        self.cmb_target_format.addItem("-- Select Target --", None)

        for fmt in FileFormat:
            if fmt in (FileFormat.UNKNOWN, source_format):
                continue
            try:
                plan = ConversionPlanner.plan_conversion(source_format, fmt)
                if plan:
                    label = fmt.value
                    if plan.has_experimental:
                        label += "  ⚠ (Experimental)"
                    self.cmb_target_format.addItem(label, fmt)
            except PlannerError:
                # This format is unreachable from source — skip silently
                pass

        self.cmb_target_format.setCurrentIndex(0)
        self._update_plan_display(None)
        self._on_inputs_updated()

    def _on_target_format_changed(self, index: int):
        """Updates plan previews and warning badges as target indices cycle."""
        if index <= 0:
            self._update_plan_display(None)
            self._on_inputs_updated()
            return

        target_format = self.cmb_target_format.itemData(index)
        if not target_format:
            return

        src_path = self.txt_source_path.text()
        dest_dir = self.txt_dest_path.text()
        out_name = self.txt_output_name.text()

        dest_file = ""
        if dest_dir and out_name:
            dest_file = str(Path(dest_dir) / f"{out_name}.{target_format.value.lower()}")

        try:
            plan = ConversionPlanner.plan_conversion(
                self.detected_format, target_format, src_path, dest_file
            )
            self.current_plan = plan
            self._update_plan_display(plan)
        except PlannerError as e:
            logger.warning(f"Plan failed: {e}")
            self.current_plan = None
            self._update_plan_display(None)

        self._on_inputs_updated()

    def _update_plan_display(self, plan: ConversionPlan | None):
        """Renders plan summaries inside the text preview block."""
        self.txt_plan_preview.clear()
        if not plan:
            self.lbl_warning_badge.setVisible(False)
            return

        self.lbl_warning_badge.setVisible(plan.has_experimental)
        report = ConversionService.generate_dry_run_report(plan)
        self.txt_plan_preview.setText(report)

    def _on_browse_dest(self):
        """Launches native directory browser to select output destination."""
        dirpath = QFileDialog.getExistingDirectory(
            self,
            "Select Output Destination Directory",
            ""
        )
        if not dirpath:
            return

        logger.info(f"Destination folder selected: {dirpath}")
        self.txt_dest_path.setText(dirpath)
        self._slot_append_log(
            f"<font color='#94a3b8'>[SYSTEM]: Set destination folder: {dirpath}</font>"
        )

        if not self.txt_output_name.text() and self.txt_source_path.text():
            src_name = Path(self.txt_source_path.text()).stem
            self.txt_output_name.setText(f"{src_name}_converted")

        self._trigger_replan()

    def _trigger_replan(self):
        """Forces the planner to recalculate output paths when inputs change."""
        idx = self.cmb_target_format.currentIndex()
        if idx > 0:
            self._on_target_format_changed(idx)

    def _on_inputs_updated(self, *args):
        """Evaluates whether all requirements are fulfilled to unlock 'Run'."""
        has_source = bool(self.txt_source_path.text())
        has_target = self.cmb_target_format.currentIndex() > 0
        has_dest = bool(self.txt_dest_path.text())
        has_name = bool(self.txt_output_name.text())
        has_plan = self.current_plan is not None

        can_run = has_source and has_target and has_dest and has_name and has_plan
        self.btn_run.setEnabled(can_run)

    # =========================================================================
    # Run / Cancel — Real Worker Execution
    # =========================================================================

    def _on_run_clicked(self):
        """Validates pre-flight conditions and launches the ConversionWorker thread."""
        if not self.current_plan:
            QMessageBox.warning(self, "No Plan", "Please select a valid source and target first.")
            return

        logger.info("Run Conversion button pressed.")

        dest_dir = self.txt_dest_path.text()
        out_name = self.txt_output_name.text()
        target_fmt = self.cmb_target_format.currentData()

        if not target_fmt:
            QMessageBox.warning(self, "No Target", "Please select a target format.")
            return

        dest_file = Path(dest_dir) / f"{out_name}.{target_fmt.value.lower()}"

        # --- Pre-flight: overwrite check ---
        if dest_file.exists():
            confirm = DialogHelper.show_overwrite_warning(self, str(dest_file))
            if not confirm:
                self._slot_append_log(
                    "<font color='orange'><b>[WARNING]: Execution cancelled: "
                    "Overwrite declined by investigator.</b></font>"
                )
                return

        # --- Pre-flight: write access check ---
        if not ConversionService.verify_write_access(dest_dir):
            QMessageBox.critical(
                self,
                "Write Access Denied",
                f"Cannot write to destination folder:\n{dest_dir}\n\n"
                "Please choose a different output directory."
            )
            return

        # --- Pre-flight: disk space check ---
        source_size = 0
        src_path = self.txt_source_path.text()
        if src_path:
            try:
                source_size = Path(src_path).stat().st_size
            except OSError:
                pass

        # Estimate: source + all intermediate + output (worst case: n_steps × source_size)
        estimated_bytes = source_size * (self.current_plan.total_steps + 1)
        if estimated_bytes > 0 and not ConversionService.check_disk_space(
            str(dest_file), estimated_bytes
        ):
            avail_gb = 0.0
            try:
                import shutil
                _, _, free = shutil.disk_usage(dest_dir)
                avail_gb = free / (1024 ** 3)
            except Exception:
                pass
            required_gb = estimated_bytes / (1024 ** 3)
            confirm = DialogHelper.show_space_warning(self, required_gb, avail_gb)
            if not confirm:
                self._slot_append_log(
                    "<font color='orange'><b>[WARNING]: Execution cancelled: "
                    "Low space safeguard triggered.</b></font>"
                )
                return

        # --- Dry run path (no real execution) ---
        if self.chk_dry_run.isChecked():
            self._run_dry_mode()
            return

        # --- Experimental path confirmation ---
        if self.current_plan.has_experimental:
            reply = QMessageBox.warning(
                self,
                "Experimental Conversion Path",
                "This conversion path is marked EXPERIMENTAL.\n\n"
                "It may fail, produce incomplete output, or behave unexpectedly.\n\n"
                "Do you wish to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._slot_append_log(
                    "<font color='orange'>[WARNING]: Experimental conversion aborted by investigator.</font>"
                )
                return

        # --- Launch real worker ---
        self._launch_conversion_worker()

    def _run_dry_mode(self):
        """Executes a Dry Run — logs all planned commands without invoking any subprocess."""
        self._slot_append_log(
            "<font color='#f59e0b'><b>[DRY RUN]: Simulating sequential pipeline execution...</b></font>"
        )
        for step in self.current_plan.steps:
            self._slot_append_log(
                f"<font color='#06b6d4'>[DRY RUN] Step {step.step_num}: "
                f"{' '.join(step.command_args)}</font>"
            )
        self.progress_bar.setValue(100)
        self._slot_append_log(
            "<font color='green'><b>[SUCCESS]: Dry run simulation complete. "
            "No files were modified.</b></font>"
        )
        self.status_bar.showMessage("Dry Run completed")

    def _launch_conversion_worker(self):
        """Creates the ConversionWorker, wires all signals, and starts the thread."""
        self._set_ui_processing(True)
        self.progress_bar.setValue(0)
        self._slot_append_log(
            "<b>[SYSTEM]: Beginning forensic processing sequence...</b>"
        )

        worker = ConversionWorker(self.current_plan, parent=self)
        self._active_worker = worker

        # Wire worker signals to GUI slots (all executed on the main thread via queued connections)
        worker.log_received.connect(self._slot_append_log)
        worker.progress_updated.connect(self._slot_update_progress)
        worker.step_started.connect(self._slot_step_started)
        worker.step_completed.connect(self._slot_step_completed)
        worker.conversion_started.connect(self._slot_conversion_started)
        worker.conversion_completed.connect(self._slot_conversion_completed)
        worker.conversion_failed.connect(self._slot_conversion_failed)
        worker.cancelled.connect(self._slot_conversion_cancelled)

        # Clean up thread handle once the thread object finishes
        worker.finished.connect(self._slot_worker_finished)

        worker.start()
        logger.info("ConversionWorker thread started.")

    def _on_cancel_clicked(self):
        """Sends a cancellation signal to the active worker thread."""
        logger.info("Cancel button clicked.")
        if self._active_worker and self._active_worker.isRunning():
            self._slot_append_log(
                "<font color='orange'><b>[WARNING]: Cancellation request sent to worker thread. "
                "Waiting for process to terminate...</b></font>"
            )
            self._active_worker.cancel()
            self.btn_cancel.setEnabled(False)   # Prevent double-click
            self.status_bar.showMessage("Cancelling — please wait...")
        else:
            self._set_ui_processing(False)
            self.status_bar.showMessage("Conversion cancelled")

    # =========================================================================
    # Worker Signal Slots — all called on the GUI main thread
    # =========================================================================

    def _slot_append_log(self, html_line: str):
        """Appends an HTML-formatted line to the log pane."""
        self.txt_log_pane.append(html_line)

    def _slot_update_progress(self, percent: int):
        """Updates the progress bar value."""
        self.progress_bar.setValue(max(0, min(100, percent)))

    def _slot_conversion_started(self, plan: ConversionPlan):
        """Handles the conversion_started signal."""
        self.status_bar.showMessage(
            f"Conversion running — {plan.total_steps} step(s) planned..."
        )

    def _slot_step_started(self, step_num: int):
        """Handles the step_started signal."""
        self.status_bar.showMessage(
            f"Step {step_num}/{self.current_plan.total_steps if self.current_plan else '?'} running..."
        )

    def _slot_step_completed(self, step_num: int):
        """Handles the step_completed signal."""
        logger.info(f"Step {step_num} completed signal received by MainWindow.")

    def _slot_conversion_completed(self, success: bool):
        """Handles the conversion_completed signal — resets UI and triggers hashing."""
        if success:
            self._slot_append_log(
                "<font color='green'><b>[SUCCESS]: All conversion steps completed successfully. "
                "Launching integrity verification...</b></font>"
            )
            self.status_bar.showMessage("Conversion complete — verifying integrity...")
            self._launch_hash_workers()
        else:
            self._set_ui_processing(False)
            self.status_bar.showMessage("Conversion failed or cancelled.")

    def _slot_conversion_failed(self, error_msg: str):
        """Handles the conversion_failed signal — shows critical error dialog."""
        self._set_ui_processing(False)
        self.status_bar.showMessage("Conversion FAILED")
        QMessageBox.critical(
            self,
            "Conversion Failed",
            f"A fatal error occurred during conversion:\n\n{error_msg}\n\n"
            "Check the log pane for full details. Any intermediate files have been cleaned up."
        )

    def _slot_conversion_cancelled(self):
        """Handles the cancelled signal from the worker."""
        self._slot_append_log(
            "<font color='orange'><b>[CANCELLED]: Conversion was stopped by the investigator.</b></font>"
        )
        self._set_ui_processing(False)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Conversion cancelled by investigator")

    def _slot_worker_finished(self):
        """Called when the QThread itself finishes — releases the thread handle."""
        logger.info("ConversionWorker thread finished. Releasing handle.")
        self._active_worker = None

    # =========================================================================
    # Hash Workers — post-conversion integrity verification
    # =========================================================================

    def _launch_hash_workers(self):
        """Launches source and output hash workers on the global QThreadPool."""
        src_path = self.txt_source_path.text()
        if not self.current_plan:
            return
        out_path = self.current_plan.steps[-1].output_file

        # Reset hash fields and show progress bar
        self.txt_hash_src_md5.clear()
        self.txt_hash_src_sha256.clear()
        self.txt_hash_out_md5.clear()
        self.txt_hash_out_sha256.clear()
        self.hash_progress_bar.setValue(0)
        self._hash_progress_row_widget.setVisible(True)
        self._hash_workers_pending = 0

        self._slot_append_log(
            "<font color='#94a3b8'>[HASH]: Computing source file hash...</font>"
        )
        src_worker = HashWorker(src_path)
        src_worker.signals.hash_progress.connect(
            lambda pct: self._slot_hash_progress(pct, "Source")
        )
        src_worker.signals.hash_completed.connect(self._slot_source_hash_done)
        src_worker.signals.hash_failed.connect(
            lambda msg: self._slot_append_log(
                f"<font color='orange'>[HASH WARNING]: Source hash failed: {msg}</font>"
            )
        )
        self._thread_pool.start(src_worker)
        self._hash_workers_pending += 1

        if out_path:
            self._slot_append_log(
                "<font color='#94a3b8'>[HASH]: Computing output file hash...</font>"
            )
            out_worker = HashWorker(out_path)
            out_worker.signals.hash_progress.connect(
                lambda pct: self._slot_hash_progress(pct, "Output")
            )
            out_worker.signals.hash_completed.connect(self._slot_output_hash_done)
            out_worker.signals.hash_failed.connect(
                lambda msg: self._slot_append_log(
                    f"<font color='orange'>[HASH WARNING]: Output hash failed: {msg}</font>"
                )
            )
            self._thread_pool.start(out_worker)
            self._hash_workers_pending += 1

    def _slot_hash_progress(self, percent: int, label: str):
        """Updates the hash verification progress bar."""
        self.lbl_hash_status.setText(f"Hashing {label}...")
        self.hash_progress_bar.setValue(max(0, min(100, percent)))

    def _slot_source_hash_done(self, result: HashResult):
        """Populates source hash fields after the HashWorker completes."""
        self.txt_hash_src_md5.setText(result.md5)
        self.txt_hash_src_sha256.setText(result.sha256)
        self._slot_append_log(
            f"<font color='green'>[HASH]: Source MD5: {result.md5}</font>"
        )
        self._slot_append_log(
            f"<font color='green'>[HASH]: Source SHA-256: {result.sha256}</font>"
        )
        self._hash_workers_pending -= 1
        self._check_hash_comparison()
        if self._hash_workers_pending <= 0:
            self._hash_progress_row_widget.setVisible(False)
            self._set_ui_processing(False)
            self.status_bar.showMessage("Conversion and verification complete.")

    def _slot_output_hash_done(self, result: HashResult):
        """Populates output hash fields after the HashWorker completes."""
        self.txt_hash_out_md5.setText(result.md5)
        self.txt_hash_out_sha256.setText(result.sha256)
        self._slot_append_log(
            f"<font color='green'>[HASH]: Output MD5: {result.md5}</font>"
        )
        self._slot_append_log(
            f"<font color='green'>[HASH]: Output SHA-256: {result.sha256}</font>"
        )
        self._hash_workers_pending -= 1
        self._check_hash_comparison()
        if self._hash_workers_pending <= 0:
            self._hash_progress_row_widget.setVisible(False)
            self._set_ui_processing(False)
            self.status_bar.showMessage("Conversion and verification complete.")

    def _check_hash_comparison(self):
        """Compares source and output hashes and logs the integrity verdict."""
        src_md5 = self.txt_hash_src_md5.text()
        out_md5 = self.txt_hash_out_md5.text()
        src_sha = self.txt_hash_src_sha256.text()
        out_sha = self.txt_hash_out_sha256.text()

        # Both need to be populated before we can compare
        if not (src_md5 and out_md5 and src_sha and out_sha):
            return

        # Note: source and output hashes will almost NEVER match for format conversions
        # (the binary format is different). This comparison is for same-format copies only.
        # We log both regardless for the chain-of-custody record.
        self._slot_append_log(
            "<font color='#06b6d4'><b>[INTEGRITY]: Hash computation complete. "
            "Both source and output checksums recorded in log for chain-of-custody.</b></font>"
        )

    # =========================================================================
    # UI Control Helpers
    # =========================================================================

    def _on_dry_run_toggled(self, state: int):
        """Toggles Dry Run mode indicator."""
        is_dry = (state == Qt.CheckState.Checked.value)
        if is_dry:
            self._slot_append_log(
                "<font color='#f59e0b'><b>[INFO]: Dry Run Mode enabled. No files will be modified.</b></font>"
            )
        else:
            self._slot_append_log(
                "<font color='#94a3b8'>[INFO]: Dry Run Mode disabled.</font>"
            )

    def _on_clear_clicked(self):
        """Wipes all controls, logs, and telemetry widgets back to initial state."""
        logger.info("Clearing Dashboard.")

        # Guard: don't clear while a conversion is running
        if self._active_worker and self._active_worker.isRunning():
            QMessageBox.warning(
                self,
                "Conversion Running",
                "Please cancel the active conversion before clearing the dashboard."
            )
            return

        self.txt_source_path.clear()
        self.txt_dest_path.clear()
        self.txt_output_name.clear()
        self.cmb_target_format.clear()
        self.txt_plan_preview.clear()
        self.txt_log_pane.clear()
        self.progress_bar.setValue(0)

        self.txt_hash_src_md5.clear()
        self.txt_hash_src_sha256.clear()
        self.txt_hash_out_md5.clear()
        self.txt_hash_out_sha256.clear()

        self.lbl_detected_badge.setText("DETECTED: UNKNOWN")
        self.lbl_detected_badge.setStyleSheet(
            "background-color: #475569; color: #ffffff; border-radius: 4px; "
            "padding: 3px 8px; font-size: 11px; font-weight: bold;"
        )
        self.lbl_warning_badge.setVisible(False)

        self.detected_format = FileFormat.UNKNOWN
        self.current_plan = None
        self._active_worker = None

        self._on_inputs_updated()
        self.status_bar.showMessage("System Ready")

    def _set_ui_processing(self, is_processing: bool):
        """Locks/unlocks interactive inputs during active background execution."""
        self.btn_browse_source.setEnabled(not is_processing)
        self.cmb_target_format.setEnabled(not is_processing)
        self.btn_browse_dest.setEnabled(not is_processing)
        self.txt_output_name.setEnabled(not is_processing)
        self.chk_dry_run.setEnabled(not is_processing)
        self.btn_clear.setEnabled(not is_processing)
        self.btn_run.setEnabled(not is_processing and self.cmb_target_format.currentIndex() > 0)
        self.btn_cancel.setEnabled(is_processing)

    def _show_about_dialog(self):
        """Displays About information popup."""
        logger.info("Opening About dialog.")
        QMessageBox.about(
            self,
            "About B.R.I.D.G.E.",
            "B.R.I.D.G.E.\n"
            "Byte-level Routing for Image Data Graphical Extension\n\n"
            "An enterprise desktop tool engineered for automated multi-step forensic conversion "
            "pipelines, safe external CLI tool runners, and chunk-streamed cryptographic "
            "verifications.\n\n"
            "Built with PySide6 & Python 3.14."
        )
