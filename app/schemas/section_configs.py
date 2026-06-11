from __future__ import annotations
from pydantic import BaseModel, HttpUrl, field_validator, model_validator
from typing import Optional, List, Any


class VideoConfig(BaseModel):
    youtube_url: Optional[str] = None
    video_path:  Optional[str] = None   # Supabase Storage path
    autoplay:    bool = False

    @model_validator(mode="after")
    def at_least_one_source(self):
        if not self.youtube_url and not self.video_path:
            raise ValueError("يجب توفير رابط YouTube أو مسار الفيديو")
        return self

    model_config = {"extra": "forbid"}


class QuizConfig(BaseModel):
    exam_id:          str
    duration_minutes: int = 30

    @field_validator("duration_minutes")
    @classmethod
    def valid_duration(cls, v):
        if v < 1 or v > 480:
            raise ValueError("المدة يجب أن تكون بين 1 و 480 دقيقة")
        return v

    model_config = {"extra": "forbid"}


class HomeworkConfig(BaseModel):
    hw_id:    str
    deadline: Optional[str] = None
    model_config = {"extra": "forbid"}


class UploadConfig(BaseModel):
    title:         str
    allowed_types: List[str] = ["pdf", "jpg", "jpeg", "png"]
    max_mb:        int = 10

    @field_validator("max_mb")
    @classmethod
    def valid_size(cls, v):
        if v < 1 or v > 100:
            raise ValueError("الحجم الأقصى يجب أن يكون بين 1 و 100 ميغابايت")
        return v

    model_config = {"extra": "forbid"}


class PDFConfig(BaseModel):
    file_path:      str
    title:          str
    allow_download: bool = True
    bucket:         str = "notes"
    model_config = {"extra": "forbid"}


class LinkItem(BaseModel):
    label: str
    url:   str
    desc:  Optional[str] = None


class LinkConfig(BaseModel):
    links: List[LinkItem]

    @field_validator("links")
    @classmethod
    def not_empty(cls, v):
        if not v:
            raise ValueError("يجب إضافة رابط واحد على الأقل")
        return v

    model_config = {"extra": "forbid"}


class FileItem(BaseModel):
    name:   str
    path:   str
    bucket: str = "attachments"
    size:   Optional[str] = None


class AttachmentConfig(BaseModel):
    files: List[FileItem]
    model_config = {"extra": "forbid"}


class DiscussionConfig(BaseModel):
    prompt:          Optional[str] = None
    allow_anonymous: bool = False
    model_config = {"extra": "forbid"}


# ── Registry ──────────────────────────────────────────────────
CONFIG_SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "video":           VideoConfig,
    "hw_review_video": VideoConfig,
    "quiz":            QuizConfig,
    "homework":        HomeworkConfig,
    "hw_upload":       UploadConfig,
    "pdf_notes":       PDFConfig,
    "links":           LinkConfig,
    "attachments":     AttachmentConfig,
    "discussion":      DiscussionConfig,
}


def validate_section_config(type_key: str, config: dict) -> dict:
    """Validate and return cleaned config dict. Raises ValueError on invalid."""
    schema = CONFIG_SCHEMA_MAP.get(type_key)
    if not schema:
        raise ValueError(f"نوع القسم غير معروف: {type_key}")
    return schema(**config).model_dump()
