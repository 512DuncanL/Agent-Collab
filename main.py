import asyncio

from fastapi import FastAPI
from aiocache import SimpleMemoryCache
from aiocache.serializers import PickleSerializer

from agent_collab import Project

app = FastAPI()

projects = SimpleMemoryCache(serializer=PickleSerializer()) # TODO: use RedisCache

@app.post("/create_project")
async def create_project(objective: str, max_iterations: int, total_agents: int, project_id: str | None) -> dict[str, str]:
    project = Project(objective=objective, max_iterations=max_iterations, total_agents=total_agents, project_id=project_id)

    if project_id is not None:
        await projects.set(project_id, project)

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