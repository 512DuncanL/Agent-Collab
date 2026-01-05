import asyncio

from fastapi import FastAPI
from aiocache import SimpleMemoryCache
from aiocache.serializers import PickleSerializer
from pydantic import BaseModel

from agent_collab import Project

app = FastAPI()

projects = SimpleMemoryCache(serializer=PickleSerializer()) # TODO: use RedisCache

class CreateProjectRequest(BaseModel):
    objective: str
    max_iterations: int
    total_agents: int
    project_id: str | None = None

@app.post("/create_project")
async def create_project(req: CreateProjectRequest) -> dict[str, str]:
    project = Project(objective=req.objective, max_iterations=req.max_iterations, total_agents=req.total_agents, project_id=req.project_id)

    if req.project_id is not None:
        await projects.set(req.project_id, project)

    asyncio.create_task(project.execute())

    return {"status": "started"}

@app.post("/pause_project")
async def pause_project(project_id: str) -> dict[str, str]:
    if not projects.exists(project_id):
        return {"error": "project not found"}

    project = await projects.get(project_id)
    project.pause()

    return {"status": "paused"}

@app.post("/resume_project")
async def resume_project(project_id: str) -> dict[str, str]:
    if not projects.exists(project_id):
        return {"error": "project not found"}

    project = await projects.get(project_id)
    project.resume()

    return {"status": "resumed"}