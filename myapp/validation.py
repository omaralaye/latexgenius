from pydantic import BaseModel, field_validator, EmailStr
from typing import Optional
import re
from urllib.parse import urlparse


ALLOWED_EXTENSIONS = {'.tex', '.md', '.markdown', '.docx', '.odt', '.html', '.txt'}
ALLOWED_PERMISSIONS = {'read', 'write', 'admin'}
ALLOWED_FONT_SIZES = {'12px', '14px', '16px', '18px'}


class SignupSchema(BaseModel):
    email: str
    password: str
    name: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        v = v.strip()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError('Invalid email format')
        if len(v) > 254:
            raise ValueError('Email too long')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if len(v) > 128:
            raise ValueError('Password too long')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        v = v.strip()
        if len(v) > 100:
            raise ValueError('Name too long')
        return v


class ProfileUpdateSchema(BaseModel):
    first_name: str = ''
    last_name: str = ''
    email: str = ''
    bio: str = ''
    avatar_url: str = ''
    affiliation: str = ''
    website: str = ''
    github: str = ''
    google_scholar: str = ''

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v:
            v = v.strip()
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
                raise ValueError('Invalid email format')
            if len(v) > 254:
                raise ValueError('Email too long')
        return v

    @field_validator('first_name')
    @classmethod
    def validate_first_name(cls, v):
        if len(v) > 100:
            raise ValueError('First name too long')
        return v

    @field_validator('last_name')
    @classmethod
    def validate_last_name(cls, v):
        if len(v) > 100:
            raise ValueError('Last name too long')
        return v

    @field_validator('bio')
    @classmethod
    def validate_bio(cls, v):
        if len(v) > 2000:
            raise ValueError('Bio too long')
        return v

    @field_validator('affiliation')
    @classmethod
    def validate_affiliation(cls, v):
        if len(v) > 200:
            raise ValueError('Affiliation too long')
        return v

    @field_validator('github')
    @classmethod
    def validate_github(cls, v):
        if len(v) > 100:
            raise ValueError('GitHub username too long')
        return v

    @field_validator('avatar_url', 'website', 'google_scholar')
    @classmethod
    def validate_url_safe(cls, v):
        if v:
            v = v.strip()
            if len(v) > 500:
                raise ValueError('URL too long')
            parsed = urlparse(v)
            if parsed.scheme and parsed.scheme not in ('http', 'https'):
                raise ValueError('URL must use http or https scheme')
        return v


class PasswordChangeSchema(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if len(v) > 128:
            raise ValueError('Password too long')
        return v


class AIConvertSchema(BaseModel):
    content: Optional[str] = None
    template_id: str

    @field_validator('template_id')
    @classmethod
    def validate_template_id(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('Template ID is required')
        if len(v) > 100:
            raise ValueError('Invalid template ID')
        return v

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        if v and len(v) > 100000:
            raise ValueError('Content too long (max 100KB)')
        return v


class SavePreferencesSchema(BaseModel):
    dark_mode: Optional[bool] = None
    auto_compile: Optional[bool] = None
    font_size: Optional[str] = None

    @field_validator('font_size')
    @classmethod
    def validate_font_size(cls, v):
        if v is not None and v not in ALLOWED_FONT_SIZES:
            raise ValueError(f'Invalid font size. Must be one of: {", ".join(sorted(ALLOWED_FONT_SIZES))}')
        return v


class CreateVersionSchema(BaseModel):
    content: Optional[str] = None
    message: str = 'Auto-save version'

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        if v and len(v) > 500000:
            raise ValueError('Content too long (max 500KB)')
        return v

    @field_validator('message')
    @classmethod
    def validate_message(cls, v):
        if len(v) > 500:
            raise ValueError('Message too long')
        return v


class ShareInvitationSchema(BaseModel):
    email: str
    permission: str = 'read'

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        v = v.strip()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError('Invalid email format')
        if len(v) > 254:
            raise ValueError('Email too long')
        return v

    @field_validator('permission')
    @classmethod
    def validate_permission(cls, v):
        if v not in ALLOWED_PERMISSIONS:
            raise ValueError(f'Invalid permission. Must be one of: {", ".join(sorted(ALLOWED_PERMISSIONS))}')
        return v


class SaveProjectSchema(BaseModel):
    content: Optional[str] = None
    title: Optional[str] = None

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        if v and len(v) > 500000:
            raise ValueError('Content too long (max 500KB)')
        return v

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if v and len(v) > 200:
            raise ValueError('Title too long')
        return v


class CheckoutSessionSchema(BaseModel):
    price_id: str

    @field_validator('price_id')
    @classmethod
    def validate_price_id(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('Price ID is required')
        if len(v) > 100:
            raise ValueError('Invalid price ID')
        return v


def validate_file_extension(filename):
    if not filename:
        return False
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS


def get_file_content_type_risk(filename):
    _, ext = os.path.splitext(filename.lower())
    high_risk_exts = {'.docx', '.odt', '.html'}
    return ext in high_risk_exts


import os
