# ui/message_manager_improved.py
"""
Improved Message Manager with consistent UI and background threading
"""

from ui.base_manager import BaseManager
from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem, QPushButton, QTextEdit, QVBoxLayout, QDialog, QDialogButtonBox, QSplitter
from PyQt6.QtCore import Qt
import os

class MessagePreviewDialog(QDialog):
    """Dialog for previewing/editing messages"""
    
    def __init__(self, message_content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Message Preview")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Split view for HTML and plain text
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # HTML preview
        self.html_edit = QTextEdit()
        self.html_edit.setPlainText(message_content)
        splitter.addWidget(self.html_edit)
        
        # Plain text version
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(self._html_to_text(message_content))
        splitter.addWidget(self.text_edit)
        
        layout.addWidget(splitter)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML to plain text (simple version)"""
        import re
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_content)
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        return text.strip()
    
    def get_message(self) -> str:
        """Get edited message content"""
        return self.html_edit.toPlainText()

class MessageManagerImproved(BaseManager):
    """Improved Message Manager with threading and consistent UI"""
    
    def __init__(self, parent=None):
        super().__init__(
            manager_type="message",
            data_subdir="messages",
            file_extension="",  # Folder-based
            parent=parent
        )
        
        # Message-specific headers
        self.default_headers = [
            "Subject", "Type", "Size", "Variables", "Modified", "Status"
        ]
    
    def _create_toolbar(self):
        """Create message-specific toolbar"""
        toolbar_layout = super()._create_toolbar()
        
        # Add message-specific buttons
        btn_preview = QPushButton("👁 Preview Message")
        btn_preview.setToolTip("Preview selected message")
        btn_preview.clicked.connect(self._preview_message)
        btn_preview.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        
        btn_new_message = QPushButton("✉ New Message")
        btn_new_message.setToolTip("Create new message template")
        btn_new_message.clicked.connect(self._create_new_message)
        
        btn_validate = QPushButton("✓ Validate HTML")
        btn_validate.setToolTip("Validate message HTML/templates")
        btn_validate.clicked.connect(self._validate_messages)
        
        # Insert before the stretch
        toolbar_layout.insertWidget(toolbar_layout.count() - 2, btn_preview)
        toolbar_layout.insertWidget(toolbar_layout.count() - 2, btn_new_message)
        toolbar_layout.insertWidget(toolbar_layout.count() - 2, btn_validate)
        
        return toolbar_layout
    
    def _create_new_list_structure(self, list_name: str):
        """Create new message list structure"""
        # Create folder for message list
        list_folder = os.path.join(self.data_dir, list_name)
        os.makedirs(list_folder, exist_ok=True)
        
        # Create sample message file
        sample_path = os.path.join(list_folder, "welcome_message.html")
        with open(sample_path, 'w', encoding='utf-8') as f:
            f.write(self._get_sample_message())
    
    def _get_sample_message(self) -> str:
        """Get sample message content"""
        return """<!DOCTYPE html>
<html>
<head>
    <title>Welcome</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; }
        .header { background-color: #f4f4f4; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .footer { background-color: #333; color: white; padding: 10px; text-align: center; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Welcome {{first_name}}!</h1>
    </div>
    <div class="content">
        <p>Dear {{first_name}} {{last_name}},</p>
        <p>Welcome to our newsletter! We're excited to have you as part of our community.</p>
        <p>Your company {{company}} has been noted in our records.</p>
        <p>Best regards,<br>The Team</p>
    </div>
    <div class="footer">
        <p>&copy; 2024 Our Company. All rights reserved.</p>
    </div>
</body>
</html>"""
    
    def _get_list_data_path(self, list_name: str) -> str:
        """Get path to message list folder"""
        return os.path.join(self.data_dir, list_name)
    
    def _get_item_count(self, list_name: str) -> int:
        """Get the number of messages in a list"""
        try:
            list_path = self._get_list_data_path(list_name)
            if os.path.isdir(list_path):
                return len([f for f in os.listdir(list_path) 
                           if os.path.isfile(os.path.join(list_path, f)) and 
                           (f.endswith('.html') or f.endswith('.txt'))])
        except Exception:
            pass
        return 0
    
    def _load_list_data(self, list_name: str):
        """Load message data for a specific list"""
        try:
            list_path = self._get_list_data_path(list_name)
            
            if os.path.isdir(list_path):
                self.headers = self.default_headers.copy()
                self.current_data = []
                
                # Scan message files in the folder
                for filename in os.listdir(list_path):
                    file_path = os.path.join(list_path, filename)
                    if os.path.isfile(file_path) and (filename.endswith('.html') or filename.endswith('.txt')):
                        try:
                            # Read file content for analysis
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            file_size = os.path.getsize(file_path)
                            file_mtime = os.path.getmtime(file_path)
                            modified_date = self._format_timestamp(file_mtime)
                            
                            # Analyze content
                            subject = self._extract_subject(content, filename)
                            msg_type = "HTML" if filename.endswith('.html') else "Text"
                            size_str = self._format_file_size(file_size)
                            variables = self._find_variables(content)
                            status = "✅ Ready" if content.strip() else "❌ Empty"
                            
                            message_data = [
                                subject,           # Subject
                                msg_type,         # Type
                                size_str,         # Size
                                variables,        # Variables
                                modified_date,    # Modified
                                status           # Status
                            ]
                            self.current_data.append(message_data)
                            
                        except Exception as e:
                            # Add error entry
                            message_data = [
                                filename, "Error", "0 B", "", "", f"❌ Error: {str(e)}"
                            ]
                            self.current_data.append(message_data)
                
                self._update_table()
            else:
                # Create empty folder and data
                os.makedirs(list_path, exist_ok=True)
                self._create_empty_list_data()
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load message data:\n{str(e)}")
            self._create_empty_list_data()
    
    def _create_empty_list_data(self):
        """Create empty message data structure"""
        self.headers = self.default_headers.copy()
        self.current_data = []
        self._update_table()
    
    def _extract_subject(self, content: str, filename: str) -> str:
        """Extract subject from message content or filename"""
        import re
        
        # Try to find title tag
        title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()
        
        # Try to find h1 tag
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.IGNORECASE)
        if h1_match:
            h1_text = re.sub(r'<[^>]+>', '', h1_match.group(1))  # Remove inner tags
            return h1_text.strip()
        
        # Use filename without extension
        return os.path.splitext(filename)[0].replace('_', ' ').title()
    
    def _find_variables(self, content: str) -> str:
        """Find template variables in content"""
        import re
        
        # Find variables like {{variable}} or {variable}
        variables = re.findall(r'\{\{?([^}]+)\}?\}', content)
        
        if variables:
            # Remove duplicates and format
            unique_vars = list(set(var.strip() for var in variables))
            return ", ".join(sorted(unique_vars)[:3])  # Show first 3
        
        return "None"
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def _format_timestamp(self, timestamp: float) -> str:
        """Format timestamp to readable date"""
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    
    def _preview_message(self):
        """Preview selected message"""
        current_row = self.table_widget.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Error", "Please select a message to preview!")
            return
        
        if current_row >= len(self.current_data):
            return
        
        # Find the message file
        subject = self.current_data[current_row][0]
        list_path = self._get_list_data_path(self.current_list_name)
        
        # Try to find file by subject
        message_file = None
        for filename in os.listdir(list_path):
            if filename.endswith('.html') or filename.endswith('.txt'):
                file_path = os.path.join(list_path, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if self._extract_subject(content, filename) == subject:
                    message_file = file_path
                    break
        
        if not message_file:
            QMessageBox.warning(self, "Error", "Message file not found!")
            return
        
        try:
            with open(message_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            dialog = MessagePreviewDialog(content, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Save edited content
                edited_content = dialog.get_message()
                with open(message_file, 'w', encoding='utf-8') as f:
                    f.write(edited_content)
                
                # Refresh data
                self._load_list_data(self.current_list_name)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to preview message:\n{str(e)}")
    
    def _create_new_message(self):
        """Create a new message template"""
        if not self.current_list_name:
            QMessageBox.warning(self, "Error", "Please select a message list first!")
            return
        
        from PyQt6.QtWidgets import QInputDialog
        
        # Get message name
        name, ok = QInputDialog.getText(self, "New Message", "Enter message name:")
        if not ok or not name.strip():
            return
        
        name = name.strip()
        list_path = self._get_list_data_path(self.current_list_name)
        
        # Create new message file
        filename = f"{name.replace(' ', '_').lower()}.html"
        file_path = os.path.join(list_path, filename)
        
        if os.path.exists(file_path):
            QMessageBox.warning(self, "Error", f"Message '{name}' already exists!")
            return
        
        try:
            # Create with template
            template_content = self._get_sample_message().replace("Welcome {{first_name}}!", name)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            
            # Refresh and select new message
            self._load_list_data(self.current_list_name)
            QMessageBox.information(self, "Success", f"Message '{name}' created successfully!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create message:\n{str(e)}")
    
    def _validate_messages(self):
        """Validate message HTML and templates"""
        if not self.current_data:
            QMessageBox.warning(self, "Error", "No messages to validate!")
            return
        
        issues = []
        list_path = self._get_list_data_path(self.current_list_name)
        
        for i, row in enumerate(self.current_data):
            subject = row[0]
            msg_type = row[1]
            
            # Find file
            message_file = None
            for filename in os.listdir(list_path):
                if filename.endswith('.html') or filename.endswith('.txt'):
                    file_path = os.path.join(list_path, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if self._extract_subject(content, filename) == subject:
                        message_file = file_path
                        break
            
            if not message_file:
                issues.append(f"Row {i+1} ({subject}): File not found")
                continue
                
            try:
                with open(message_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Basic validations
                if not content.strip():
                    issues.append(f"Row {i+1} ({subject}): Empty content")
                
                if msg_type == "HTML":
                    # Check for basic HTML structure
                    if '<html' not in content.lower():
                        issues.append(f"Row {i+1} ({subject}): Missing HTML structure")
                    
                    # Check for unclosed tags (basic check)
                    import re
                    tags = re.findall(r'<(/?)(\w+)[^>]*>', content)
                    tag_stack = []
                    for is_closing, tag_name in tags:
                        if is_closing:
                            if tag_stack and tag_stack[-1] == tag_name.lower():
                                tag_stack.pop()
                            else:
                                issues.append(f"Row {i+1} ({subject}): Unclosed or mismatched tag <{tag_name}>")
                        else:
                            if tag_name.lower() not in ['br', 'hr', 'img', 'input', 'meta', 'link']:
                                tag_stack.append(tag_name.lower())
                    
                    if tag_stack:
                        issues.append(f"Row {i+1} ({subject}): Unclosed tags: {', '.join(tag_stack)}")
                
                # Check for unresolved variables
                import re
                unresolved_vars = re.findall(r'\{\{([^}]+)\}\}', content)
                if unresolved_vars:
                    common_vars = ['first_name', 'last_name', 'email', 'company']
                    unusual_vars = [var for var in unresolved_vars if var.strip() not in common_vars]
                    if unusual_vars:
                        issues.append(f"Row {i+1} ({subject}): Unusual variables: {', '.join(set(unusual_vars))}")
                
            except Exception as e:
                issues.append(f"Row {i+1} ({subject}): Validation error - {str(e)}")
        
        if issues:
            message = "Validation Issues Found:\n\n" + "\n".join(issues[:10])
            if len(issues) > 10:
                message += f"\n\n... and {len(issues) - 10} more issues"
            QMessageBox.warning(self, "Validation Results", message)
        else:
            QMessageBox.information(self, "Validation Results", "All messages look good! ✅")
    
    def _update_table(self):
        """Update table with message-specific formatting"""
        super()._update_table()
        
        # Apply message-specific formatting
        for row in range(self.table_widget.rowCount()):
            # Color-code status column
            if self.table_widget.columnCount() > 5:
                status_item = self.table_widget.item(row, 5)
                if status_item:
                    status_text = status_item.text()
                    if "Ready" in status_text or "✅" in status_text:
                        status_item.setBackground(Qt.GlobalColor.green)
                    elif "Error" in status_text or "❌" in status_text:
                        status_item.setBackground(Qt.GlobalColor.red)
                    elif "Empty" in status_text:
                        status_item.setBackground(Qt.GlobalColor.yellow)
            
            # Color-code type column
            if self.table_widget.columnCount() > 1:
                type_item = self.table_widget.item(row, 1)
                if type_item:
                    msg_type = type_item.text()
                    if msg_type == "HTML":
                        type_item.setBackground(Qt.GlobalColor.lightGray)
                    elif msg_type == "Text":
                        type_item.setBackground(Qt.GlobalColor.cyan)