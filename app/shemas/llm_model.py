from pydantic import BaseModel, ConfigDict


class LLMModelShema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra='forbid')

    llm_id: str
    name: str
    context_length: int
    price_competition: float