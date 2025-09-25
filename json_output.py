from pydantic import BaseModel

class Brainstorm(BaseModel):
    message_to_team: str
    subtask_assignments: list[list[str, str], ...]
    vote: bool

class Discuss(BaseModel):
    message_to_team: str
    subtask_assignments: list[list[str, str], ...]
    end_discussion_vote: bool
    complete_project_vote: bool