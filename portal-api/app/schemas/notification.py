from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime


class MailTemplateOut(BaseModel):
    key: str
    subject: str
    body_html: str


class MailTemplateUpdateIn(BaseModel):
    subject: str
    body_html: str
