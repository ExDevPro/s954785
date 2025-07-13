"""
Data models for Bulk Email Sender.

This module defines data structures used throughout the application:
- Lead data structure
- SMTP configuration model
- Campaign configuration
- Message templates
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum
import json

from core.utils.helpers import generate_unique_id, normalize_email, is_valid_email
from core.utils.logger import get_module_logger

logger = get_module_logger(__name__)


class EmailStatus(Enum):
    """Email sending status enumeration."""
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"
    CANCELLED = "cancelled"


class LeadStatus(Enum):
    """Lead general status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    OPTED_OUT = "opted_out"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"


class CampaignStatus(Enum):
    """Campaign status enumeration."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SMTPSecurityType(Enum):
    """SMTP security type enumeration."""
    NONE = "none"
    TLS = "tls"
    SSL = "ssl"


class SMTPStatus(Enum):
    """SMTP connection status enumeration."""
    UNTESTED = "untested"
    TESTING = "testing"
    WORKING = "working"
    FAILED = "failed"


class TemplateStatus(Enum):
    """Template status enumeration."""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class TemplateVariableType(Enum):
    """Template variable type enumeration."""
    TEXT = "text"
    EMAIL = "email"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"


@dataclass
class TemplateVariable:
    """Template variable data structure."""
    
    name: str
    type: TemplateVariableType = TemplateVariableType.TEXT
    required: bool = True
    default_value: Optional[str] = None
    description: str = ""
    
    def __post_init__(self):
        """Validate variable after initialization."""
        if not self.name:
            raise ValueError("Variable name is required")
        
        # Normalize name (remove spaces, convert to lowercase)
        self.name = self.name.strip().lower().replace(' ', '_')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert variable to dictionary."""
        return {
            'name': self.name,
            'type': self.type.value,
            'required': self.required,
            'default_value': self.default_value,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TemplateVariable':
        """Create variable from dictionary."""
        if 'type' in data and isinstance(data['type'], str):
            data['type'] = TemplateVariableType(data['type'])
        return cls(**data)


@dataclass
class Lead:
    """Lead data structure."""
    
    email: str
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    title: str = ""
    phone: str = ""
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # Metadata
    id: str = field(default_factory=generate_unique_id)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: LeadStatus = LeadStatus.ACTIVE
    
    # Email status tracking
    email_status: EmailStatus = EmailStatus.PENDING
    last_email_sent: Optional[datetime] = None
    send_attempts: int = 0
    last_error: Optional[str] = None
    
    def __post_init__(self):
        """Validate and normalize data after initialization."""
        self.email = normalize_email(self.email)
        if not is_valid_email(self.email):
            raise ValueError(f"Invalid email address: {self.email}")
        
        # Ensure names are properly formatted
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        self.company = self.company.strip()
        self.title = self.title.strip()
        self.phone = self.phone.strip()
    
    @property
    def full_name(self) -> str:
        """Get full name from first and last name."""
        parts = [self.first_name, self.last_name]
        return " ".join(part for part in parts if part).strip()
    
    @property
    def display_name(self) -> str:
        """Get display name for email (full name or email if no name)."""
        full_name = self.full_name
        return full_name if full_name else self.email
    
    def get_custom_field(self, field_name: str, default: Any = None) -> Any:
        """Get custom field value."""
        return self.custom_fields.get(field_name, default)
    
    def set_custom_field(self, field_name: str, value: Any) -> None:
        """Set custom field value."""
        self.custom_fields[field_name] = value
        self.updated_at = datetime.now()
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the lead."""
        tag = tag.strip().lower()
        if tag and tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now()
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the lead."""
        tag = tag.strip().lower()
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.now()
    
    def has_tag(self, tag: str) -> bool:
        """Check if lead has a specific tag."""
        return tag.strip().lower() in self.tags
    
    def update_email_status(self, status: EmailStatus, error: Optional[str] = None) -> None:
        """Update email sending status."""
        self.email_status = status
        self.updated_at = datetime.now()
        
        if status == EmailStatus.SENT:
            self.last_email_sent = datetime.now()
        elif status == EmailStatus.FAILED and error:
            self.last_error = error
            self.send_attempts += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert lead to dictionary."""
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'company': self.company,
            'title': self.title,
            'phone': self.phone,
            'custom_fields': self.custom_fields,
            'tags': self.tags,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'status': self.status.value,
            'email_status': self.email_status.value,
            'last_email_sent': self.last_email_sent.isoformat() if self.last_email_sent else None,
            'send_attempts': self.send_attempts,
            'last_error': self.last_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Lead':
        """Create lead from dictionary."""
        # Handle datetime fields
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'last_email_sent' in data and data['last_email_sent']:
            data['last_email_sent'] = datetime.fromisoformat(data['last_email_sent'])
        
        # Handle enum fields
        if 'email_status' in data and isinstance(data['email_status'], str):
            data['email_status'] = EmailStatus(data['email_status'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = LeadStatus(data['status'])
        
        return cls(**data)


@dataclass
class SMTPConfig:
    """SMTP configuration data structure."""
    
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True
    security_type: SMTPSecurityType = SMTPSecurityType.TLS
    timeout: int = 30
    
    # Metadata
    id: str = field(default_factory=generate_unique_id)
    name: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Connection tracking
    last_tested: Optional[datetime] = None
    is_verified: bool = False
    last_error: Optional[str] = None
    status: SMTPStatus = SMTPStatus.UNTESTED
    
    # Rate limiting
    max_emails_per_hour: Optional[int] = None
    max_emails_per_day: Optional[int] = None
    delay_between_emails: float = 1.0
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.host:
            raise ValueError("SMTP host is required")
        if not (1 <= self.port <= 65535):
            raise ValueError("SMTP port must be between 1 and 65535")
        if not self.username:
            raise ValueError("SMTP username is required")
        if not self.password:
            raise ValueError("SMTP password is required")
        
        if not self.name:
            self.name = f"{self.username}@{self.host}:{self.port}"
    
    def update_verification_status(self, is_verified: bool, error: Optional[str] = None) -> None:
        """Update verification status."""
        self.is_verified = is_verified
        self.last_tested = datetime.now()
        self.updated_at = datetime.now()
        
        if not is_verified and error:
            self.last_error = error
        elif is_verified:
            self.last_error = None
    
    def to_dict(self, include_password: bool = False) -> Dict[str, Any]:
        """Convert SMTP config to dictionary."""
        data = {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'use_tls': self.use_tls,
            'security_type': self.security_type.value,
            'timeout': self.timeout,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_tested': self.last_tested.isoformat() if self.last_tested else None,
            'is_verified': self.is_verified,
            'last_error': self.last_error,
            'status': self.status.value,
            'max_emails_per_hour': self.max_emails_per_hour,
            'max_emails_per_day': self.max_emails_per_day,
            'delay_between_emails': self.delay_between_emails
        }
        
        if include_password:
            data['password'] = self.password
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SMTPConfig':
        """Create SMTP config from dictionary."""
        # Handle datetime fields
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'last_tested' in data and data['last_tested']:
            data['last_tested'] = datetime.fromisoformat(data['last_tested'])
        
        # Handle enum fields
        if 'security_type' in data and isinstance(data['security_type'], str):
            data['security_type'] = SMTPSecurityType(data['security_type'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = SMTPStatus(data['status'])
        
        return cls(**data)


@dataclass
class EmailTemplate:
    """Email template data structure."""
    
    subject: str
    html_content: str = ""
    text_content: str = ""
    
    # Metadata
    id: str = field(default_factory=generate_unique_id)
    name: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: TemplateStatus = TemplateStatus.DRAFT
    
    # Template variables
    variables: List[str] = field(default_factory=list)  # Variable names extracted from content
    template_variables: List[TemplateVariable] = field(default_factory=list)  # Detailed variable objects
    
    def __post_init__(self):
        """Process template after initialization."""
        if not self.name:
            self.name = f"Template {self.id[:8]}"
        
        # Extract variables from template content
        self._extract_variables()
    
    def _extract_variables(self) -> None:
        """Extract template variables from content."""
        import re
        
        # Find variables in format {{variable_name}}
        pattern = r'\{\{([^}]+)\}\}'
        
        variables = set()
        for content in [self.subject, self.html_content, self.text_content]:
            matches = re.findall(pattern, content)
            variables.update(var.strip() for var in matches)
        
        self.variables = sorted(list(variables))
    
    def add_variable(self, template_variable: TemplateVariable) -> None:
        """Add a template variable."""
        # Check if variable already exists
        existing_names = [var.name for var in self.template_variables]
        if template_variable.name not in existing_names:
            self.template_variables.append(template_variable)
            self.updated_at = datetime.now()
    
    def remove_variable(self, variable_name: str) -> None:
        """Remove a template variable by name."""
        self.template_variables = [var for var in self.template_variables if var.name != variable_name]
        self.updated_at = datetime.now()
    
    def get_variable(self, variable_name: str) -> Optional[TemplateVariable]:
        """Get a template variable by name."""
        for var in self.template_variables:
            if var.name == variable_name:
                return var
        return None
    
    def render(self, variables: Dict[str, Any]) -> tuple[str, str, str]:
        """
        Render template with variables.
        
        Args:
            variables: Variable values dictionary
            
        Returns:
            Tuple of (subject, html_content, text_content)
        """
        rendered_subject = self.subject
        rendered_html = self.html_content
        rendered_text = self.text_content
        
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            str_value = str(var_value) if var_value is not None else ""
            
            rendered_subject = rendered_subject.replace(placeholder, str_value)
            rendered_html = rendered_html.replace(placeholder, str_value)
            rendered_text = rendered_text.replace(placeholder, str_value)
        
        return rendered_subject, rendered_html, rendered_text
    
    def validate_variables(self, variables: Dict[str, Any]) -> List[str]:
        """
        Validate that all required variables are provided.
        
        Args:
            variables: Variable values dictionary
            
        Returns:
            List of missing variable names
        """
        missing = []
        for var in self.variables:
            if var not in variables or variables[var] is None:
                missing.append(var)
        return missing
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'subject': self.subject,
            'html_content': self.html_content,
            'text_content': self.text_content,
            'status': self.status.value,
            'variables': self.variables,
            'template_variables': [var.to_dict() for var in self.template_variables],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmailTemplate':
        """Create template from dictionary."""
        # Handle datetime fields
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        # Handle enum fields
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = TemplateStatus(data['status'])
        
        # Handle template variables
        if 'template_variables' in data and isinstance(data['template_variables'], list):
            data['template_variables'] = [TemplateVariable.from_dict(var_data) for var_data in data['template_variables']]
        
        return cls(**data)


@dataclass
class Campaign:
    """Email campaign data structure."""
    
    name: str
    template_id: str
    smtp_config_id: str
    lead_ids: List[str] = field(default_factory=list)
    
    # Metadata
    id: str = field(default_factory=generate_unique_id)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Campaign settings
    status: CampaignStatus = CampaignStatus.DRAFT
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Sending settings
    batch_size: int = 50
    delay_between_batches: float = 60.0
    max_retries: int = 3
    
    # Tracking
    total_leads: int = 0
    emails_sent: int = 0
    emails_failed: int = 0
    emails_pending: int = 0
    
    # Attachments
    attachment_paths: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Process campaign after initialization."""
        self.total_leads = len(self.lead_ids)
        self.emails_pending = self.total_leads
    
    def add_lead(self, lead_id: str) -> None:
        """Add a lead to the campaign."""
        if lead_id not in self.lead_ids:
            self.lead_ids.append(lead_id)
            self.total_leads = len(self.lead_ids)
            self.emails_pending = self.total_leads - self.emails_sent
            self.updated_at = datetime.now()
    
    def remove_lead(self, lead_id: str) -> None:
        """Remove a lead from the campaign."""
        if lead_id in self.lead_ids:
            self.lead_ids.remove(lead_id)
            self.total_leads = len(self.lead_ids)
            self.emails_pending = max(0, self.total_leads - self.emails_sent)
            self.updated_at = datetime.now()
    
    def update_status(self, status: CampaignStatus) -> None:
        """Update campaign status."""
        self.status = status
        self.updated_at = datetime.now()
        
        if status == CampaignStatus.RUNNING and not self.started_at:
            self.started_at = datetime.now()
        elif status == CampaignStatus.COMPLETED and not self.completed_at:
            self.completed_at = datetime.now()
    
    def update_progress(self, sent: int = 0, failed: int = 0) -> None:
        """Update campaign progress."""
        self.emails_sent += sent
        self.emails_failed += failed
        self.emails_pending = max(0, self.total_leads - self.emails_sent - self.emails_failed)
        self.updated_at = datetime.now()
        
        # Auto-complete if all emails processed
        if self.emails_pending == 0 and self.status == CampaignStatus.RUNNING:
            self.update_status(CampaignStatus.COMPLETED)
    
    def get_progress_percentage(self) -> float:
        """Get campaign progress as percentage."""
        if self.total_leads == 0:
            return 0.0
        return ((self.emails_sent + self.emails_failed) / self.total_leads) * 100
    
    def get_success_rate(self) -> float:
        """Get email success rate as percentage."""
        total_processed = self.emails_sent + self.emails_failed
        if total_processed == 0:
            return 0.0
        return (self.emails_sent / total_processed) * 100
    
    def add_attachment(self, file_path: str) -> None:
        """Add an attachment to the campaign."""
        if file_path not in self.attachment_paths:
            self.attachment_paths.append(file_path)
            self.updated_at = datetime.now()
    
    def remove_attachment(self, file_path: str) -> None:
        """Remove an attachment from the campaign."""
        if file_path in self.attachment_paths:
            self.attachment_paths.remove(file_path)
            self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert campaign to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'template_id': self.template_id,
            'smtp_config_id': self.smtp_config_id,
            'lead_ids': self.lead_ids,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'status': self.status.value,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'batch_size': self.batch_size,
            'delay_between_batches': self.delay_between_batches,
            'max_retries': self.max_retries,
            'total_leads': self.total_leads,
            'emails_sent': self.emails_sent,
            'emails_failed': self.emails_failed,
            'emails_pending': self.emails_pending,
            'attachment_paths': self.attachment_paths
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Campaign':
        """Create campaign from dictionary."""
        # Handle datetime fields
        datetime_fields = ['created_at', 'updated_at', 'scheduled_at', 'started_at', 'completed_at']
        for field in datetime_fields:
            if field in data and data[field]:
                data[field] = datetime.fromisoformat(data[field])
        
        # Handle enum fields
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = CampaignStatus(data['status'])
        
        return cls(**data)