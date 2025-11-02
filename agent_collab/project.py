from __future__ import annotations
import shutil
from google import genai
from os import path
from pathlib import Path
import asyncio
from uuid import uuid4
import random
import glob
import logging

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .agent import Agent

from .prompts import DEFAULT_AGENT_TRAITS

client = genai.Client()

def list_files(directory: str) -> list[str]:
    all_paths = glob.glob(f"{directory}/**/*", recursive=True)
    return sorted([path.relpath(p, directory) for p in all_paths if path.isfile(p) and not p.startswith(
        "browseruse_agent_data\\")])  # Recursively add all files but ignore auto generated browseruse_agent_data folder


class Project:
    """
    Class that manages AI agents to complete a given project.

    The system operates by first engaging in brainstorming, followed by iterative cycles of work execution and discussion:
    - Brainstorming: Agents collaboratively break down the objective into subtasks and assign them
    - Work: Agents execute their assigned tasks asynchronously
    - Discussion: Agents review progress, reassess tasks, and vote on project completion

    The project continues through iterations until either:
    - All agents vote that the objective is complete
    - The maximum number of iterations is reached
    """
    _agents: "list[Agent]"
    _conversations: list[str]
    _iteration_number: int
    _completed: bool
    _logger: logging.Logger

    def __init__(self, objective: str, max_iterations: int, total_agents: int, steps_per_work_cycle: int | list[int] = 50,
                 agent_traits: list[str] | None = None, llm_name: str | list[str] = "gemini-flash-latest", project_id: str = str(uuid4())):
        """
        Note:
            `llm_name` must be a model supported by the Gemini API
        """
        from .agent import Agent
        self._objective = objective
        self._max_iterations = max_iterations
        self._total_agents = total_agents
        self._steps_per_work_cycle = steps_per_work_cycle
        self._project_id = project_id
        self._agents = []
        self._conversations = [""]
        self._iteration_number = 1
        self._completed = False
        self._logger = logging.getLogger(project_id)

        # Set agent traits
        if agent_traits is None:
            agent_traits = random.choices(DEFAULT_AGENT_TRAITS, k=total_agents)

        if isinstance(steps_per_work_cycle, list) and len(steps_per_work_cycle) != total_agents:
            raise ValueError(f"Expected `steps_per_work_cycle` to be a list with length equal to the total number of agents ({total_agents}), but got {len(steps_per_work_cycle)}.")
        else:
            steps_per_work_cycle = [steps_per_work_cycle] * total_agents

        if isinstance(llm_name, list) and len(llm_name) != total_agents:
            raise ValueError(f"Expected `llm_name` to be a list with length equal to the total number of agents ({total_agents}), but got {len(llm_name)}.")
        else:
            llm_name = [llm_name] * total_agents

        # Add agents to project
        for i in range(total_agents):
            self.add_agent(Agent(
                _id=i,
                agent_traits=agent_traits[i],
                llm_name=llm_name[i],
                steps_per_work_cycle=steps_per_work_cycle[i],
                project=self
            ))

        # Set up project folder
        root_dir = Path(__file__).resolve().parent.parent
        self._project_dir = root_dir / project_id

        if self._project_dir.exists():
            shutil.rmtree(self._project_dir)

        self._project_dir.mkdir()
        (self._project_dir / "file_system_collab").mkdir()
        (self._project_dir / "file_system_output").mkdir()

        # Set up logging
        file_handler = logging.FileHandler(self.project_dir / "logfile.log")
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] - %(levelname)s: %(message)s"))

        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)

    @property
    def total_agents(self) -> int:
        return self._total_agents

    @property
    def project_id(self) -> str:
        return self._project_id

    @property
    def objective(self) -> str:
        return self._objective

    @property
    def steps_per_work_cycle(self) -> int:
        return self._steps_per_work_cycle

    @property
    def project_dir(self) -> Path:
        return self._project_dir

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    @property
    def max_iterations(self) -> int:
        return self._max_iterations

    @property
    def iteration_number(self) -> int:
        return self._iteration_number

    @iteration_number.setter
    def iteration_number(self, value) -> None:
        self._iteration_number = value

    def add_agent(self, agent: Agent) -> None:
        self._agents.append(agent)

    def get_current_files(self) -> str:
        current_files = f"Output File System: {', '.join(list_files(f'{self.project_dir}/file_system_output'))}\nCollaborative File System: {', '.join(list_files(f'{self.project_dir}/file_system_collab'))}"
        for agent in self._agents:
            current_files += f"\nAgent {agent.agent_id}'s Private File System: " + ", ".join(
                list_files(f"{self.project_dir}/file_system_{agent.agent_id}"))

        return current_files

    def get_full_agent_task_history(self) -> str:
        """All previous task descriptions + actions for most recent task"""
        full_agent_task_history = ""
        for agent in self._agents:
            executed_tasks, outputs = agent.task_history

            assert len(executed_tasks) == len(outputs), f"agent {agent.agent_id}'s tasks: {len(executed_tasks), executed_tasks}, outputs: {len(outputs), outputs}"  # Sanity check

            full_agent_task_history += f"Agent_{agent.agent_id}'s completed tasks and task outputs:\n"
            for i in range(len(executed_tasks)):
                full_agent_task_history += f"Description of task {i} of Agent_{agent.agent_id}: {executed_tasks[i]}\n\n"

            full_agent_task_history += f"\nActions completed for task {len(executed_tasks) - 1} of Agent_{agent.agent_id}: {outputs[len(executed_tasks) - 1]}\n---\n\n"

        return full_agent_task_history

    async def brainstorm_round(self) -> None:
        current_agent = 0
        votes = 0
        subtask_assignments = None

        while votes < self.total_agents:

            brainstorm_result = await asyncio.to_thread(
                self._agents[current_agent].brainstorm,
                objective=self.objective,
                current_conversation=self._conversations[-1]
            )

            self.logger.info(f"Conversation: {brainstorm_result}")

            self._conversations[-1] += f"{brainstorm_result.message_to_team}\nMy proposed subtask assignments: {brainstorm_result.subtask_assignments}\n---\n"

            subtask_assignments = brainstorm_result.subtask_assignments
            votes += brainstorm_result.vote
            current_agent = current_agent + 1 if current_agent < self.total_agents - 1 else 0

        for i, agent_name in enumerate(subtask_assignments):
            if i >= self.total_agents:
                break  # Stop reading tasks after we reach the number of total agents (sometimes LLM output contains extra irrelevant info)

            agent_id = int(agent_name[6:])
            self._agents[agent_id].add_task(subtask_assignments[agent_name])

            self.logger.info(f"Assigned tasks for agent {agent_id}: {agent_name} {subtask_assignments[agent_name]}")

    async def work_round(self) -> None:
        work = [agent.work() for agent in self._agents]

        await asyncio.gather(*work, return_exceptions=True)

    async def discussion_round(self) -> None:
        DISCUSSION_LIMIT = self.total_agents * 8
        current_agent = 0
        discussion_votes = 0
        project_votes = 0
        discussion_round = 1 # Increments by one per "speech"
        subtask_assignments = None

        # We add all previous task descriptions + actions for most recent task to context
        full_agent_task_history = self.get_full_agent_task_history()

        self.logger.debug(f"Full task history: {full_agent_task_history}")

        # List out all files in files all file systems
        current_files = self.get_current_files()

        self.logger.debug(f"Current files: {current_files}")

        while discussion_votes < self.total_agents and discussion_round < DISCUSSION_LIMIT:
            discuss_result = await asyncio.to_thread(
                self._agents[current_agent].discuss,
                task_history=full_agent_task_history,
                current_files=current_files,
                current_conversation=self._conversations[-1],
            )

            self.logger.debug(f"Discussion object from Agent_{current_agent}: {discuss_result}")

            self._conversations[-1] += f"{discuss_result.message_to_team}\nMy proposed subtask assignments: {discuss_result.subtask_assignments}\n---\n"

            subtask_assignments = discuss_result.subtask_assignments

            discussion_votes = discussion_votes + discuss_result.end_discussion_vote if discuss_result.end_discussion_vote else 0
            project_votes = project_votes + discuss_result.complete_project_vote if discuss_result.complete_project_vote else 0  # Reset vote counter if an agent disagrees

            current_agent = current_agent + 1 if current_agent < self.total_agents - 1 else 0

            if project_votes >= self.total_agents: # End discussion if project is complete
                self._completed = True
                return

            discussion_round += 1

        # Assign subtasks to agents based on discussion results
        for i, agent_name in enumerate(subtask_assignments):
            if i >= self.total_agents:
                break  # Stop reading tasks after we reach the number of total agents (sometimes LLM output contains extra irrelevant info)

            agent_id = int(agent_name[6:])
            self._agents[agent_id].add_task(subtask_assignments[agent_name])

            self.logger.info(f"Assigned tasks for agent {agent_id}: {agent_name} {subtask_assignments[agent_name]}")

    async def execute(self) -> None:
        await self.brainstorm_round()
        await self.work_round()
        for _ in range(self.max_iterations - 1):
            self.iteration_number += 1
            await self.discussion_round()

            if self._completed:
                break

            await self.work_round()

        self.logger.info(f"The project objective has been completed after {self.iteration_number - 1} iterations of work.")