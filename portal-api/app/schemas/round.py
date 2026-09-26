from datetime import datetime

from pydantic import BaseModel

from app.models.round import ParticipationStatus, ReportChannel, RoundStatus


class RoundCreateIn(BaseModel):
    name: str
    survey_version_id: int
    start_at: datetime
    end_at: datetime
    reminder_days_before_end: list[int] = [7, 2]
    report_channel: ReportChannel = ReportChannel.portal
    target_fachbereiche: list[str] | None = None


class RoundOut(BaseModel):
    id: int
    name: str
    survey_version_id: int
    status: RoundStatus
    start_at: datetime
    end_at: datetime
    reminder_days_before_end: list[int]
    report_channel: ReportChannel
    target_fachbereiche: list[str] | None


class RoundTargetOut(BaseModel):
    id: int
    leader_person_id: int
    leader_name: str
    leader_code: str
    team_size_snapshot: int
    evaluable: bool
    completed_count: int
    open_count: int


class RoundDashboardOut(BaseModel):
    round_id: int
    status: RoundStatus
    total_invited: int
    total_completed: int
    response_rate: float
    by_fachbereich: dict[str, dict[str, float | int]]
    targets: list[RoundTargetOut]


class MyFeedbackOut(BaseModel):
    participation_id: int
    round_name: str
    leader_name: str
    status: ParticipationStatus
    due_date: str
    feedback_link: str | None
    completed_date: str | None
