from agent_collab import Project
import asyncio

async def main():
    project_1 = Project(
        objective="First conduct research on the effects of tobacco on children, and then create a full stack website on it using Flask as the backend. Keep the original file extension behind the `.txt` extension. No matter the file type, the extension should always end with `.txt`. For example, the main python file could be named `main.py.txt`.",
        max_iterations=3,
        total_agents=3,
        project_id="tobacco"
    )
    project_2 = Project(
        objective="Obtain data on youth unemployment and mental health in Canada. Find any relevant correlations using statistical tests and write a comprehensive academic report on them. Remember to cite sources.",
        max_iterations=2,
        total_agents=3,
        project_id="youth"
    )

    await asyncio.gather(
        project_1.execute(),
        project_2.execute()
    )

if __name__ == "__main__":
    asyncio.run(main())