from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Identifier = Annotated[str, StringConstraints(min_length=1, max_length=128, strip_whitespace=True)]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,31}$")]
Limit = Annotated[int, Field(ge=1, le=50)]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TasteRequest(Body):
    domain: Slug
    liked: list[Identifier] = Field(default_factory=list, max_length=20)
    model: Slug | None = None
    k: Limit = 10
    diversify: bool = True


class CrossRequest(Body):
    source_domain: Slug
    target_domain: Slug
    liked: list[Identifier] = Field(min_length=1, max_length=20)
    method: Literal["text", "tfidf", "hybrid"] = "hybrid"
    k: Limit = 10
    diversify: bool = True


class FeedRequest(Body):
    favorites: dict[Slug, Annotated[list[Identifier], Field(min_length=1, max_length=5)]] = Field(
        min_length=1, max_length=10
    )
    k: Annotated[int, Field(ge=1, le=10)] = 4


class FeedbackRequest(Body):
    domain: Slug
    item_id: Identifier
    vote: Literal["up", "down"]


class Item(BaseModel):
    item_id: str
    titre: str
    description: str
    domaine: str
    tags: list[str]
    image: str
    year: str
    source: str = ""
    source_url: str = ""


class Recommendation(Item):
    score: float
    explanation: str


class RecommendationList(BaseModel):
    domain: str
    model: str
    recommendations: list[Recommendation]


class FeedResult(BaseModel):
    groups: list[RecommendationList]


class Catalog(BaseModel):
    total: int
    items: list[Item]
