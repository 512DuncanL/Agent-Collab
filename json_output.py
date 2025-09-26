from pydantic import BaseModel

class Brainstorm(BaseModel):
    message_to_team: str
    subtask_assignments: dict[str, str]
    vote: bool

class Discuss(BaseModel):
    message_to_team: str
    subtask_assignments: dict[str, str]
    end_discussion_vote: bool
    complete_project_vote: bool