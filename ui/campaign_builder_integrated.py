# ui/campaign_builder_integrated.py
"""
Integrated campaign builder using new foundation architecture.

This module provides the GUI for campaign management using:
- New campaign models (core.data.models.Campaign)
- New worker system (workers.base_worker)
- New email engine integration
- New validation and error handling
- Centralized logging
"""

from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QComboBox, QRadioButton, QGroupBox,
    QHBoxLayout, QVBoxLayout, QGridLayout, QMessageBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QTextEdit,
    QSplitter, QListWidget, QInputDialog, QSpacerItem, QSizePolicy,
    QFormLayout, QDialog, QDialogButtonBox, QLineEdit, QCheckBox, QDateTimeEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QDateTime

import os
import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Import new foundation components
from core.data.models import Campaign, CampaignStatus, Lead, SMTPConfig, EmailTemplate
from core.data.file_handler import FileHandler
from core.validation.data_validator import DataValidator
from core.utils.logger import get_module_logger
from core.utils.exceptions import handle_exception, ValidationError, FileError
from workers.base_worker import BaseWorker, WorkerProgress, WorkerStatus
from core.engine.smtp_client import EmailSender

logger = get_module_logger(__name__)


class CampaignWorker(BaseWorker):
    """Worker for campaign operations using new foundation."""
    
    campaign_loaded = pyqtSignal(object)  # Campaign
    campaign_saved = pyqtSignal(bool, str)  # success, message
    email_sent = pyqtSignal(str, bool, str)  # recipient, success, message
    campaign_completed = pyqtSignal(object, dict)  # campaign, results
    
    def __init__(self):
        super().__init__(name="campaign_worker")
        self.file_handler = FileHandler()
        self.data_validator = DataValidator()
        
        # Operation parameters
        self.operation = None
        self.campaign = None
        self.file_path = None
        self.leads = None
        self.smtp_configs = None
        self.email_template = None
    
    def load_campaign(self, file_path: str):
        """Load campaign from file."""
        self.operation = "load"
        self.file_path = file_path
        self.start()
    
    def save_campaign(self, campaign: Campaign, file_path: str):
        """Save campaign to file."""
        self.operation = "save"
        self.campaign = campaign
        self.file_path = file_path
        self.start()
    
    def execute_campaign(self, campaign: Campaign, leads: List[Lead], 
                        smtp_configs: List[SMTPConfig], email_template: EmailTemplate):
        """Execute campaign sending."""
        self.operation = "execute"
        self.campaign = campaign
        self.leads = leads
        self.smtp_configs = smtp_configs
        self.email_template = email_template
        self.start()
    
    def _execute(self, *args, **kwargs) -> Any:
        """Execute the work based on operation type (required by BaseWorker)."""
        return self.execute_work()
    
    def execute_work(self) -> Any:
        """Execute the work based on operation type."""
        try:
            if self.operation == "load":
                return self._load_campaign()
            elif self.operation == "save":
                return self._save_campaign()
            elif self.operation == "execute":
                return self._execute_campaign()
            else:
                raise ValueError(f"Unknown operation: {self.operation}")
                
        except Exception as e:
            handle_exception(e, f"Error in campaign worker operation: {self.operation}")
            raise
    
    def _load_campaign(self) -> Campaign:
        """Load campaign from file."""
        logger.info("Loading campaign from file", file_path=self.file_path)
        
        try:
            data = self.file_handler.load_json(self.file_path)
            
            # Convert dict to Campaign object
            campaign = Campaign(
                name=data.get('name', 'Unnamed Campaign'),
                description=data.get('description', ''),
                status=CampaignStatus(data.get('status', 'draft'))
            )
            
            # Set other properties
            if 'created_date' in data:
                campaign.created_date = datetime.fromisoformat(data['created_date'])
            if 'scheduled_date' in data:
                campaign.scheduled_date = datetime.fromisoformat(data['scheduled_date'])
            
            campaign.settings = data.get('settings', {})
            campaign.tags = data.get('tags', [])
            
            logger.info("Campaign loaded successfully", name=campaign.name)
            self.campaign_loaded.emit(campaign)
            return campaign
            
        except Exception as e:
            error_msg = f"Failed to load campaign: {e}"
            logger.error(error_msg)
            raise FileError(error_msg)
    
    def _save_campaign(self) -> bool:
        """Save campaign to file."""
        logger.info("Saving campaign to file", name=self.campaign.name, file_path=self.file_path)
        
        try:
            data = {
                'name': self.campaign.name,
                'description': self.campaign.description,
                'status': self.campaign.status.value,
                'created_date': self.campaign.created_date.isoformat(),
                'scheduled_date': self.campaign.scheduled_date.isoformat() if self.campaign.scheduled_date else None,
                'settings': self.campaign.settings,
                'tags': self.campaign.tags
            }
            
            self.file_handler.save_json(self.file_path, data)
            
            logger.info("Campaign saved successfully")
            self.campaign_saved.emit(True, "Campaign saved successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to save campaign: {e}"
            logger.error(error_msg)
            self.campaign_saved.emit(False, error_msg)
            raise FileError(error_msg)
    
    def _execute_campaign(self) -> Dict[str, Any]:
        """Execute campaign sending."""
        logger.info("Executing campaign", name=self.campaign.name, 
                   leads_count=len(self.leads), smtp_count=len(self.smtp_configs))
        
        results = {
            'total_emails': len(self.leads),
            'sent_successfully': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            # Update campaign status
            self.campaign.status = CampaignStatus.RUNNING
            
            # Get campaign settings
            settings = self.campaign.settings
            delay_between_emails = settings.get('delay_between_emails', 1)
            randomize_delay = settings.get('randomize_delay', False)
            batch_size = settings.get('batch_size', 1)
            
            # Prepare SMTP senders
            smtp_senders = []
            for smtp_config in self.smtp_configs:
                try:
                    sender = EmailSender(smtp_config)
                    smtp_senders.append(sender)
                except Exception as e:
                    logger.warning("Failed to create SMTP sender", host=smtp_config.host, error=str(e))
                    continue
            
            if not smtp_senders:
                raise ValidationError("No valid SMTP configurations available")
            
            # Send emails
            for idx, lead in enumerate(self.leads):
                if self.is_cancelled():
                    break
                
                # Update progress
                progress = int((idx / len(self.leads)) * 100)
                self._update_progress(idx, len(self.leads), 
                                   f"Sending email {idx + 1} of {len(self.leads)}")
                
                try:
                    # Select SMTP sender (round-robin)
                    sender = smtp_senders[idx % len(smtp_senders)]
                    
                    # Send email
                    success = sender.send_template_email(self.email_template, lead)
                    
                    if success:
                        results['sent_successfully'] += 1
                        self.email_sent.emit(lead.email, True, "Sent successfully")
                        logger.info("Email sent successfully", recipient=lead.email)
                    else:
                        results['failed'] += 1
                        error_msg = "Failed to send email"
                        results['errors'].append(f"{lead.email}: {error_msg}")
                        self.email_sent.emit(lead.email, False, error_msg)
                        logger.warning("Email sending failed", recipient=lead.email)
                    
                    # Apply delay
                    if delay_between_emails > 0 and idx < len(self.leads) - 1:
                        actual_delay = delay_between_emails
                        if randomize_delay:
                            # Add random variation (±30%)
                            variation = delay_between_emails * 0.3
                            actual_delay = delay_between_emails + random.uniform(-variation, variation)
                        
                        # Sleep in small chunks to allow cancellation
                        sleep_chunks = max(1, int(actual_delay * 10))  # 0.1 second chunks
                        for _ in range(sleep_chunks):
                            if self.is_cancelled():
                                break
                            self.sleep(0.1)
                    
                except Exception as e:
                    results['failed'] += 1
                    error_msg = f"Error sending to {lead.email}: {e}"
                    results['errors'].append(error_msg)
                    self.email_sent.emit(lead.email, False, str(e))
                    logger.error("Email sending error", recipient=lead.email, error=str(e))
            
            # Update campaign status
            if self.is_cancelled():
                self.campaign.status = CampaignStatus.CANCELLED
            else:
                self.campaign.status = CampaignStatus.COMPLETED
            
            logger.info("Campaign execution completed", 
                       successful=results['sent_successfully'], 
                       failed=results['failed'])
            
            self.campaign_completed.emit(self.campaign, results)
            return results
            
        except Exception as e:
            self.campaign.status = CampaignStatus.CANCELLED
            error_msg = f"Campaign execution failed: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            self.campaign_completed.emit(self.campaign, results)
            raise


class IntegratedCampaignBuilder(QWidget):
    """Integrated campaign builder using new foundation."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Campaign Builder")
        
        # Initialize foundation components
        self.file_handler = FileHandler()
        self.data_validator = DataValidator()
        
        # Setup paths
        base_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        self.campaigns_dir = os.path.join(base_path, 'data', 'campaigns')
        os.makedirs(self.campaigns_dir, exist_ok=True)
        
        # Current state
        self.current_campaign: Optional[Campaign] = None
        self.current_campaign_file = None
        
        # Worker for background operations
        self.worker = None
        
        # Available data
        self.available_leads: List[Lead] = []
        self.available_smtps: List[SMTPConfig] = []
        self.available_templates: List[EmailTemplate] = []
        
        # Setup UI
        self.setup_ui()
        self.refresh_campaign_list()
        self.load_available_data()
        
        logger.info("Integrated campaign builder initialized")
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Campaign list
        left_panel = self.create_campaign_list_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Campaign configuration
        right_panel = self.create_configuration_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setStretchFactor(0, 0)  # Left panel fixed
        splitter.setStretchFactor(1, 1)  # Right panel stretches
        splitter.setSizes([300, 800])
        
        layout.addWidget(splitter)
    
    def create_campaign_list_panel(self):
        """Create the campaign list panel."""
        panel = QWidget()
        panel.setMaximumWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        title = QLabel("<b>Campaigns</b>")
        layout.addWidget(title)
        
        # Campaign list
        self.campaign_list = QListWidget()
        self.campaign_list.currentItemChanged.connect(self.on_campaign_selected)
        layout.addWidget(self.campaign_list)
        
        # List controls
        controls = QGridLayout()
        
        btn_new = QPushButton("➕ New")
        btn_new.setToolTip("Create new campaign")
        btn_new.clicked.connect(self.create_new_campaign)
        controls.addWidget(btn_new, 0, 0)
        
        btn_delete = QPushButton("🗑️ Delete")
        btn_delete.setToolTip("Delete selected campaign")
        btn_delete.clicked.connect(self.delete_campaign)
        controls.addWidget(btn_delete, 0, 1)
        
        btn_duplicate = QPushButton("📋 Copy")
        btn_duplicate.setToolTip("Duplicate selected campaign")
        btn_duplicate.clicked.connect(self.duplicate_campaign)
        controls.addWidget(btn_duplicate, 1, 0)
        
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setToolTip("Refresh campaign list")
        btn_refresh.clicked.connect(self.refresh_campaign_list)
        controls.addWidget(btn_refresh, 1, 1)
        
        layout.addLayout(controls)
        
        return panel
    
    def create_configuration_panel(self):
        """Create the campaign configuration panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Campaign info section
        info_group = QGroupBox("Campaign Information")
        info_layout = QFormLayout(info_group)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter campaign name")
        self.name_edit.textChanged.connect(self.on_campaign_info_changed)
        info_layout.addRow("Name:", self.name_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("Enter campaign description")
        self.description_edit.textChanged.connect(self.on_campaign_info_changed)
        info_layout.addRow("Description:", self.description_edit)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Draft", "Scheduled", "Running", "Paused", "Completed", "Cancelled"])
        self.status_combo.currentTextChanged.connect(self.on_campaign_info_changed)
        info_layout.addRow("Status:", self.status_combo)
        
        layout.addWidget(info_group)
        
        # Data selection section
        data_group = QGroupBox("Data Selection")
        data_layout = QFormLayout(data_group)
        
        self.leads_combo = QComboBox()
        self.leads_combo.addItem("Select leads list...")
        data_layout.addRow("Leads:", self.leads_combo)
        
        self.smtp_combo = QComboBox()
        self.smtp_combo.addItem("Select SMTP config...")
        data_layout.addRow("SMTP:", self.smtp_combo)
        
        self.template_combo = QComboBox()
        self.template_combo.addItem("Select email template...")
        data_layout.addRow("Template:", self.template_combo)
        
        layout.addWidget(data_group)
        
        # Settings section
        settings_group = QGroupBox("Campaign Settings")
        settings_layout = QFormLayout(settings_group)
        
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 3600)
        self.delay_spin.setValue(1)
        self.delay_spin.setSuffix(" seconds")
        settings_layout.addRow("Delay between emails:", self.delay_spin)
        
        self.randomize_delay_check = QCheckBox("Randomize delay (±30%)")
        settings_layout.addRow("", self.randomize_delay_check)
        
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 1000)
        self.batch_size_spin.setValue(1)
        settings_layout.addRow("Batch size:", self.batch_size_spin)
        
        self.scheduled_datetime = QDateTimeEdit()
        self.scheduled_datetime.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.scheduled_datetime.setCalendarPopup(True)
        settings_layout.addRow("Scheduled time:", self.scheduled_datetime)
        
        layout.addWidget(settings_group)
        
        # Action buttons
        actions_layout = QHBoxLayout()
        
        self.btn_save = QPushButton("💾 Save Campaign")
        self.btn_save.clicked.connect(self.save_campaign)
        self.btn_save.setEnabled(False)
        actions_layout.addWidget(self.btn_save)
        
        self.btn_test = QPushButton("🧪 Test Send")
        self.btn_test.clicked.connect(self.test_campaign)
        self.btn_test.setEnabled(False)
        actions_layout.addWidget(self.btn_test)
        
        self.btn_start = QPushButton("🚀 Start Campaign")
        self.btn_start.clicked.connect(self.start_campaign)
        self.btn_start.setEnabled(False)
        actions_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("⏹ Stop Campaign")
        self.btn_stop.clicked.connect(self.stop_campaign)
        self.btn_stop.setEnabled(False)
        actions_layout.addWidget(self.btn_stop)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        # Progress section
        progress_group = QGroupBox("Campaign Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.status_label)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        progress_layout.addWidget(self.log_text)
        
        layout.addWidget(progress_group)
        
        layout.addStretch()
        
        return panel
    
    def refresh_campaign_list(self):
        """Refresh the campaign list."""
        try:
            self.campaign_list.clear()
            
            for filename in os.listdir(self.campaigns_dir):
                if filename.endswith('.json'):
                    campaign_name = filename[:-5]  # Remove .json extension
                    self.campaign_list.addItem(campaign_name)
            
            logger.info("Campaign list refreshed", count=self.campaign_list.count())
            
        except Exception as e:
            handle_exception(e, "Failed to refresh campaign list")
            QMessageBox.warning(self, "Error", f"Failed to refresh campaign list: {e}")
    
    def load_available_data(self):
        """Load available leads, SMTPs, and templates."""
        try:
            base_path = os.path.dirname(os.path.dirname(__file__))
            data_dir = os.path.join(base_path, 'data')
            
            # TODO: Load actual data from integrated managers
            # For now, just populate with placeholder data
            
            self.leads_combo.clear()
            self.leads_combo.addItem("No leads lists available")
            
            self.smtp_combo.clear()
            self.smtp_combo.addItem("No SMTP configs available")
            
            self.template_combo.clear()
            self.template_combo.addItem("No email templates available")
            
            logger.info("Available data loaded")
            
        except Exception as e:
            handle_exception(e, "Failed to load available data")
    
    def on_campaign_selected(self, current, previous):
        """Handle campaign selection."""
        if not current:
            self.clear_campaign_form()
            return
        
        campaign_name = current.text()
        campaign_file = os.path.join(self.campaigns_dir, f"{campaign_name}.json")
        
        if os.path.exists(campaign_file):
            self.load_campaign_from_file(campaign_file)
    
    def load_campaign_from_file(self, file_path: str):
        """Load campaign from file using worker."""
        try:
            self.current_campaign_file = file_path
            self.status_label.setText("Loading campaign...")
            
            # Create and start worker
            self.worker = CampaignWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.campaign_loaded.connect(self.on_campaign_loaded)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.load_campaign(file_path)
            
        except Exception as e:
            handle_exception(e, "Failed to start campaign loading")
            QMessageBox.critical(self, "Error", f"Failed to load campaign: {e}")
    
    def on_campaign_loaded(self, campaign: Campaign):
        """Handle campaign loaded from worker."""
        self.current_campaign = campaign
        self.populate_campaign_form(campaign)
        self.enable_campaign_actions()
        
        logger.info("Campaign loaded in UI", name=campaign.name)
    
    def populate_campaign_form(self, campaign: Campaign):
        """Populate form with campaign data."""
        self.name_edit.setText(campaign.name)
        self.description_edit.setPlainText(campaign.description)
        
        # Set status
        status_text = campaign.status.value.title()
        index = self.status_combo.findText(status_text)
        if index >= 0:
            self.status_combo.setCurrentIndex(index)
        
        # Set settings
        settings = campaign.settings
        self.delay_spin.setValue(settings.get('delay_between_emails', 1))
        self.randomize_delay_check.setChecked(settings.get('randomize_delay', False))
        self.batch_size_spin.setValue(settings.get('batch_size', 1))
        
        if campaign.scheduled_date:
            self.scheduled_datetime.setDateTime(campaign.scheduled_date)
    
    def clear_campaign_form(self):
        """Clear the campaign form."""
        self.current_campaign = None
        self.current_campaign_file = None
        
        self.name_edit.clear()
        self.description_edit.clear()
        self.status_combo.setCurrentIndex(0)
        
        self.delay_spin.setValue(1)
        self.randomize_delay_check.setChecked(False)
        self.batch_size_spin.setValue(1)
        self.scheduled_datetime.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        
        self.disable_campaign_actions()
    
    def enable_campaign_actions(self):
        """Enable campaign action buttons."""
        self.btn_save.setEnabled(True)
        
        # Enable test and start only if campaign is valid
        if self.current_campaign and self.is_campaign_valid():
            self.btn_test.setEnabled(True)
            self.btn_start.setEnabled(True)
    
    def disable_campaign_actions(self):
        """Disable campaign action buttons."""
        self.btn_save.setEnabled(False)
        self.btn_test.setEnabled(False)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(False)
    
    def is_campaign_valid(self) -> bool:
        """Check if campaign configuration is valid."""
        if not self.current_campaign:
            return False
        
        # Check basic requirements
        if not self.current_campaign.name.strip():
            return False
        
        # Check data selection
        if (self.leads_combo.currentIndex() <= 0 or
            self.smtp_combo.currentIndex() <= 0 or
            self.template_combo.currentIndex() <= 0):
            return False
        
        return True
    
    def on_campaign_info_changed(self):
        """Handle campaign information changes."""
        if not self.current_campaign:
            return
        
        # Update campaign object
        self.current_campaign.name = self.name_edit.text().strip()
        self.current_campaign.description = self.description_edit.toPlainText().strip()
        
        status_text = self.status_combo.currentText().lower()
        try:
            self.current_campaign.status = CampaignStatus(status_text)
        except ValueError:
            pass  # Invalid status, keep current
        
        # Update settings
        self.current_campaign.settings.update({
            'delay_between_emails': self.delay_spin.value(),
            'randomize_delay': self.randomize_delay_check.isChecked(),
            'batch_size': self.batch_size_spin.value()
        })
        
        self.current_campaign.scheduled_date = self.scheduled_datetime.dateTime().toPython()
        
        # Update action buttons
        if self.is_campaign_valid():
            self.enable_campaign_actions()
        else:
            self.btn_test.setEnabled(False)
            self.btn_start.setEnabled(False)
    
    def create_new_campaign(self):
        """Create a new campaign."""
        name, ok = QInputDialog.getText(self, "New Campaign", "Enter campaign name:")
        if not ok or not name.strip():
            return
        
        name = name.strip()
        campaign_file = os.path.join(self.campaigns_dir, f"{name}.json")
        
        if os.path.exists(campaign_file):
            QMessageBox.warning(self, "Error", "A campaign with this name already exists.")
            return
        
        try:
            # Create new campaign
            campaign = Campaign(
                name=name,
                description="",
                status=CampaignStatus.DRAFT
            )
            
            # Set default settings
            campaign.settings = {
                'delay_between_emails': 1,
                'randomize_delay': False,
                'batch_size': 1
            }
            
            self.current_campaign = campaign
            self.current_campaign_file = campaign_file
            
            # Save campaign
            self.save_campaign()
            
            # Refresh list and select new campaign
            self.refresh_campaign_list()
            for i in range(self.campaign_list.count()):
                if self.campaign_list.item(i).text() == name:
                    self.campaign_list.setCurrentRow(i)
                    break
            
            logger.info("New campaign created", name=name)
            
        except Exception as e:
            handle_exception(e, "Failed to create new campaign")
            QMessageBox.critical(self, "Error", f"Failed to create campaign: {e}")
    
    def delete_campaign(self):
        """Delete the selected campaign."""
        current_item = self.campaign_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a campaign to delete.")
            return
        
        campaign_name = current_item.text()
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete campaign '{campaign_name}'?\n\n"
            f"This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                campaign_file = os.path.join(self.campaigns_dir, f"{campaign_name}.json")
                if os.path.exists(campaign_file):
                    os.remove(campaign_file)
                
                # Clear form if this was the current campaign
                if self.current_campaign and self.current_campaign.name == campaign_name:
                    self.clear_campaign_form()
                
                # Refresh list
                self.refresh_campaign_list()
                
                logger.info("Campaign deleted", name=campaign_name)
                
            except Exception as e:
                handle_exception(e, "Failed to delete campaign")
                QMessageBox.critical(self, "Error", f"Failed to delete campaign: {e}")
    
    def duplicate_campaign(self):
        """Duplicate the selected campaign."""
        current_item = self.campaign_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a campaign to duplicate.")
            return
        
        original_name = current_item.text()
        
        name, ok = QInputDialog.getText(
            self, "Duplicate Campaign", 
            f"Enter new name for copy of '{original_name}':",
            text=f"{original_name}_copy"
        )
        if not ok or not name.strip():
            return
        
        name = name.strip()
        new_campaign_file = os.path.join(self.campaigns_dir, f"{name}.json")
        
        if os.path.exists(new_campaign_file):
            QMessageBox.warning(self, "Error", "A campaign with this name already exists.")
            return
        
        try:
            # Copy campaign file
            original_file = os.path.join(self.campaigns_dir, f"{original_name}.json")
            if os.path.exists(original_file):
                # Load, modify name, and save
                data = self.file_handler.load_json(original_file)
                data['name'] = name
                data['status'] = 'draft'  # Reset status
                self.file_handler.save_json(new_campaign_file, data)
                
                # Refresh list
                self.refresh_campaign_list()
                
                logger.info("Campaign duplicated", original=original_name, new=name)
            
        except Exception as e:
            handle_exception(e, "Failed to duplicate campaign")
            QMessageBox.critical(self, "Error", f"Failed to duplicate campaign: {e}")
    
    def save_campaign(self):
        """Save the current campaign."""
        if not self.current_campaign or not self.current_campaign_file:
            QMessageBox.information(self, "No Campaign", "No campaign to save.")
            return
        
        try:
            self.status_label.setText("Saving campaign...")
            
            # Update campaign from form
            self.on_campaign_info_changed()
            
            # Create and start worker
            self.worker = CampaignWorker()
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.campaign_saved.connect(self.on_campaign_saved)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.error_occurred.connect(self.on_worker_error)
            
            self.worker.save_campaign(self.current_campaign, self.current_campaign_file)
            
        except Exception as e:
            handle_exception(e, "Failed to start campaign saving")
            QMessageBox.critical(self, "Error", f"Failed to save campaign: {e}")
    
    def on_campaign_saved(self, success: bool, message: str):
        """Handle campaign save completion."""
        if success:
            logger.info("Campaign saved successfully")
        else:
            QMessageBox.critical(self, "Save Failed", f"Save failed: {message}")
    
    def test_campaign(self):
        """Test the campaign with a single email."""
        if not self.is_campaign_valid():
            QMessageBox.warning(self, "Invalid Configuration", 
                              "Please complete the campaign configuration first.")
            return
        
        QMessageBox.information(self, "Test Send", "Test send functionality not yet implemented.")
    
    def start_campaign(self):
        """Start the campaign."""
        if not self.is_campaign_valid():
            QMessageBox.warning(self, "Invalid Configuration", 
                              "Please complete the campaign configuration first.")
            return
        
        reply = QMessageBox.question(
            self, "Start Campaign",
            f"Are you sure you want to start campaign '{self.current_campaign.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Campaign Start", "Campaign execution functionality not yet implemented.")
    
    def stop_campaign(self):
        """Stop the running campaign."""
        if self.worker and not self.worker.is_finished():
            self.worker.cancel()
            self.btn_stop.setEnabled(False)
            self.status_label.setText("Stopping campaign...")
    
    def update_progress(self, progress: WorkerProgress):
        """Update progress bar from worker."""
        self.progress_bar.setValue(int(progress.percentage))
        self.status_label.setText(progress.message)
    
    def on_worker_finished(self):
        """Handle worker completion."""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready")
        self.btn_stop.setEnabled(False)
        self.worker = None
    
    def on_worker_error(self, error_message: str):
        """Handle worker error."""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Error")
        QMessageBox.critical(self, "Operation Error", error_message)
        self.btn_stop.setEnabled(False)
        self.worker = None