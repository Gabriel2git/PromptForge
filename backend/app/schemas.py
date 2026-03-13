from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


FrameworkLiteral = Literal["standard", "langgpt", "co-star", "xml"]
ModeLiteral = Literal["auto", "manual"]


class ConversationConfigInput(BaseModel):
    mode: ModeLiteral = "auto"
    scenario: Optional[str] = None
    personality: Optional[str] = None
    template: Optional[str] = None
    verbosity: int = Field(default=5, ge=1, le=10)
    framework: Optional[str] = None
    max_turns: Optional[int] = Field(default=None, ge=1, le=10)


class ResolvedConversationConfig(BaseModel):
    mode: ModeLiteral
    scenario: str
    personality: str
    template: str
    verbosity: int = Field(ge=1, le=10)
    framework: FrameworkLiteral
    confidence: float = 0.0
    matched_keywords: List[str] = Field(default_factory=list)
    reason: str = "manual"
    source: str = "manual"


class ConversationCreateRequest(BaseModel):
    initial_idea: str = Field(..., min_length=1, max_length=4000)
    framework: Optional[FrameworkLiteral] = None
    config: Optional[ConversationConfigInput] = None


class MessageCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    force_generate: bool = False


class PromptRefineRequest(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=2000)


class RethinkRequest(BaseModel):
    hint: str = Field(default="", max_length=1000)


class PromptUpdateRequest(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=20000)


class SettingsUpdateRequest(BaseModel):
    api_key: str = Field(default="", max_length=5000)
    base_url: str = Field(..., min_length=1, max_length=2000)
    model: str = Field(..., min_length=1, max_length=200)
    max_turns: int = Field(..., ge=1, le=10)
    default_framework: FrameworkLiteral


class SettingsResponse(BaseModel):
    api_key: str
    base_url: str
    model: str
    max_turns: int
    default_framework: FrameworkLiteral


class IntentClassifyRequest(BaseModel):
    initial_idea: str = Field(..., min_length=1, max_length=4000)
    threshold: float = Field(default=0.34, ge=0, le=1)


class IntentClassifyResponse(BaseModel):
    scenario: str
    recommended_personality: str
    recommended_template: str
    confidence: float
    matched_keywords: List[str] = Field(default_factory=list)
    reason: str


class PreviewSkeletonRequest(BaseModel):
    initial_idea: str = Field(default="", max_length=4000)
    config: Optional[ConversationConfigInput] = None
    framework: Optional[str] = None


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
    tags: List[str] = Field(default_factory=list)
    raw_text: str


class ConversationDetail(BaseModel):
    id: str
    created_at: str
    initial_idea: str
    status: str
    current_turn: int
    framework: FrameworkLiteral
    max_turns: int
    resolved_config: Optional[ResolvedConversationConfig] = None
    messages: List[MessageItem]
    generated_prompt: Optional[PromptResult] = None


class PromptListItem(BaseModel):
    id: str
    conversation_id: str
    updated_at: str
    framework: FrameworkLiteral
    tags: List[str] = Field(default_factory=list)
    snippet: str


class PromptListResponse(BaseModel):
    items: List[PromptListItem]
    total: int


class PromptDetailResponse(BaseModel):
    id: str
    conversation_id: str
    updated_at: str
    framework: FrameworkLiteral
    resolved_config: Optional[ResolvedConversationConfig] = None
    prompt: PromptResult


class PromptOptionsResponse(BaseModel):
    scenarios: List[dict[str, Any]]
    personalities: List[dict[str, Any]]
    templates: List[dict[str, Any]]
    compatibility_matrix: dict[str, List[str]]
