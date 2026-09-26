from pydantic import BaseModel


class LimeSurveyCompleteWebhookIn(BaseModel):
    sid: int
    token: str
    signature: str
