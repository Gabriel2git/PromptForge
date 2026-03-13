from pydantic import BaseModel, Field
from typing import List, Optional


class ConversationCreateRequest(BaseModel):
    initial_idea: str = Field(..., min_length=1, max_length=4000)


class MessageCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    force_generate: bool = False


class PromptUpdateRequest(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=20000)


class MessageItem(BaseModel):
    role: str
    content: str
    timestamp: str


class PromptResult(BaseModel):
    role: str
    task: str
    input_spec: dict
    constraints: List[str]
    output_format: str
    thinking_strategy: str
    error_handling: str
    initialization: str
    examples: List[str]
    raw_text: str


class ConversationDetail(BaseModel):
    id: str
    created_at: str
    initial_idea: str
    status: str
    current_turn: int
    messages: List[MessageItem]
    generated_prompt: Optional[PromptResult] = None
