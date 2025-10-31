from __future__ import annotations
from pathlib import Path
from browser_use import Agent as BrowserAgent, ChatGoogle, Tools, Browser
from google import genai
from google.genai import types
from os.path import isfile
from time import sleep
import pypdf

client = genai.Client()

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .project import Project

from .prompts import AGENT_SYSTEM_PROMPT, BRAINSTORM_PROMPT, DISCUSS_PROMPT
from .models import Brainstorm, Discuss

class Agent:
    _system_prompt: str
    _tasks: list[str]
    _outputs: list[str]

    def __init__(self, _id: int, agent_traits: str, llm_name: str, steps_per_work_cycle: int, project: "Project") -> None:
        self._agent_id = _id

        self._agent_traits = agent_traits
        self._project = project
        self._llm_name = llm_name
        self._steps_per_work_cycle = steps_per_work_cycle
        self._system_prompt = AGENT_SYSTEM_PROMPT.substitute(
            agent_id=self.agent_id,
            total_agents=self._project.total_agents,
            agent_traits=self._agent_traits
        )
        self._tasks = []
        self._outputs = []

    @property
    def agent_id(self) -> int:
        return self._agent_id

    @property
    def task_history(self) -> list[list[str]]:
        return [self._tasks, self._outputs]

    def add_task(self, task: str) -> None:
        self._tasks.append(task)

    def get_path(self, file_system: str) -> Path:
        if file_system == "private":
            return self._project.project_dir / f"file_system_{self.agent_id}"
        elif file_system == "collab":
            return self._project.project_dir / "file_system_collab"
        else:
            return self._project.project_dir / "file_system_output"

    def _read_file(self, filename: str, file_system: str) -> str:
        assert file_system in ["private", "collab", "output"], f"{file_system} is not a supported file system"

        path = self.get_path(file_system=file_system)

        if not filename:
            return "Error: File name was not provided."

        if len(filename.split(".")) == 1 or filename.split(".")[-1] not in ["txt", "md", "csv", "json", "pdf"]:
            return f"Error: Invalid file extension."

        if not isfile(path / filename):
            return f"Error: File {filename} was not found."

        extension = filename.split(".")[-1]

        if extension in ["txt", "md", "csv", "json"]:
            with open(path / filename, "r", encoding='utf-8') as f:
                contents = f.read()

            return f'Successfully read from {file_system} file {filename}.\n<content>\n{contents}\n</content>'
        else:  # extension is pdf
            reader = pypdf.PdfReader(path / filename)
            num_pages = len(reader.pages)
            MAX_PDF_PAGES = 15
            extra_pages = num_pages - MAX_PDF_PAGES
            extracted_text = ''

            for page in reader.pages[:MAX_PDF_PAGES]:
                extracted_text += page.extract_text()

            extra_pages_text = f'{extra_pages} more pages...' if extra_pages > 0 else ''

            return f'Successfully read from {file_system} file {filename}.\n<content>\n{extracted_text}\n{extra_pages_text}</content>'

    def _write_file(self, filename: str, contents: str, file_system: str) -> str:
        assert file_system in ["private", "collab", "output"], f"{file_system} is not a supported file system"

        path = self.get_path(file_system=file_system)

        if len(filename.split(".")) == 1 or filename.split(".")[-1] not in ["txt", "md", "csv", "json"]:
            return f"Error: Invalid file extension."

        with open(path / filename, 'w', encoding='utf-8') as f:
            f.write(contents)

        return f'Successfully wrote to {file_system} file {filename}'

    def _replace_file_str(self, filename: str, old_str: str, new_str: str, file_system: str) -> str:
        assert file_system in ["private", "collab", "output"], f"{file_system} is not a supported file system"

        path = self.get_path(file_system=file_system)

        if not filename:
            return "Error: File name was not provided."

        if len(filename.split(".")) == 1 or filename.split(".")[-1] not in ["txt", "md", "csv", "json"]:
            return f"Error: Invalid file extension."

        if not isfile(path / filename):
            return f"Error: File {filename} was not found."

        if not old_str:
            return "Error: Cannot replace empty string. Please provide a non-empty string to replace."

        with open(path / filename, 'r', encoding='utf-8') as f:
            contents = f.read()

        contents = contents.replace(old_str, new_str)

        with open(path / filename, 'w', encoding='utf-8') as f:
            f.write(contents)

        return f'Successfully replaced all occurrences of "{old_str}" with "{new_str}" in {file_system} file {filename}'

    def _create_folder(self, folder_name: str, file_system: str) -> str:
        assert file_system in ["private", "collab", "output"], f"{file_system} is not a supported file system"

        if not folder_name:
            return "Error: Folder name was not provided."

        path = self.get_path(file_system=file_system) / folder_name

        if path.exists():
            return f"Error: Folder {folder_name} already exists."

        path.mkdir()

        return f"Successfully created {file_system} folder {folder_name}"

    def brainstorm(self, objective: str, current_conversation: str) -> Brainstorm:
        brainstorm_prompt = self._system_prompt + "\n---" + BRAINSTORM_PROMPT.substitute(
            # There is no built-in system prompt for structured output
            objective=objective,
            total_agents=self._project.total_agents,
            current_conversation=current_conversation,
            agent_id=self.agent_id
        )

        attempts = 0

        while attempts < 10:
            try:
                response = client.models.generate_content(
                    model=self._llm_name,
                    contents=brainstorm_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_json_schema=Brainstorm.model_json_schema(),
                        temperature=1.5,
                    )
                )

                return Brainstorm.model_validate(response.parsed)
            except Exception as e:
                attempts += 1
                print(f"(Attempt {attempts}) Brainstorm for Agent_{self.agent_id} failed with exception: {e}")
                sleep(5)

        raise Exception(f"Brainstorming for Agent_{self.agent_id} failed")

    async def work(self) -> None:
        task = self._tasks[-1]

        tools = Tools(exclude_actions=['write_file', 'read_file', 'replace_file_str'])

        @tools.action(description='Read a file in the private file system named `filename`.')
        def read_private_file(filename: str) -> str:
            return self._read_file(filename=filename, file_system="private")

        @tools.action(description='Write `contents` to a file in the private file system named `filename`. Overwrites previous file if it already exists.')
        def write_private_file(filename: str, contents: str) -> str:
            return self._write_file(filename=filename, contents=contents, file_system="private")

        @tools.action(description='Replace `old_str` with `new_str` in a file in the private file system named `file_name`.')
        def replace_private_file_str(filename: str, old_str: str, new_str: str) -> str:
            return self._replace_file_str(filename=filename, old_str=old_str, new_str=new_str, file_system="private")

        @tools.action(description='Create a folder in the private file system named `folder_name`. Does nothing if it already exists.')
        def create_private_folder(folder_name: str) -> str:
            return self._create_folder(folder_name=folder_name, file_system="private")

        @tools.action(description='Read a file in the collaborative file system named `filename`.')
        def read_collab_file(filename: str) -> str:
            return self._read_file(filename=filename, file_system="collab")

        @tools.action(description='Write `contents` to a file in the collaborative file system named `filename`. Overwrites collaborative file if it already exists.')
        def write_collab_file(filename: str, contents: str) -> str:
            return self._write_file(filename=filename, contents=contents, file_system="collab")

        @tools.action(description='Replace `old_str` with `new_str` in a file in the collaborative file system named `file_name`.')
        def replace_collab_file_str(filename: str, old_str: str, new_str: str) -> str:
            return self._replace_file_str(filename=filename, old_str=old_str, new_str=new_str, file_system="collab")

        @tools.action(description='Create a folder in the collaborative file system named `folder_name`. Does nothing if it already exists.')
        def create_collab_folder(folder_name: str) -> str:
            return self._create_folder(folder_name=folder_name, file_system="collab")

        @tools.action(description='Read a file in the output file system named `filename`.')
        def read_output_file(filename: str) -> str:
            return self._read_file(filename=filename, file_system="output")

        @tools.action(description='Write `contents` to a file in the output file system named `filename`. Overwrites output file if it already exists.')
        def write_output_file(filename: str, contents: str) -> str:
            return self._write_file(filename=filename, contents=contents, file_system="output")

        @tools.action(description='Replace `old_str` with `new_str` in a file in the output file system named `file_name`.')
        def replace_output_file_str(filename: str, old_str: str, new_str: str) -> str:
            return self._replace_file_str(filename=filename, old_str=old_str, new_str=new_str, file_system="output")

        @tools.action(description='Create a folder in the output file system named `folder_name`. Does nothing if it already exists.')
        def create_output_folder(folder_name: str) -> str:
            return self._create_folder(folder_name=folder_name, file_system="output")

        browser = Browser(
            downloads_path=f"{self._project.project_dir}/file_system_{self.agent_id}",
            window_size={'width': 1280, 'height': 800}
            # ,user_data_dir=f'{self._project.project_dir}/agent_profile_{self.agent_id}'
        )
        browser_llm = ChatGoogle(model=self._llm_name, temperature=0.8)
        browser_agent = BrowserAgent(
            task=task,
            llm=browser_llm, tools=tools,
            available_file_paths=[f"{self._project.project_dir}/file_system_{self.agent_id}", f"{self._project.project_dir}/file_system_collab", f"{self._project.project_dir}/file_system_output"],
            file_system_path=f"{self._project.project_dir}/file_system_{self.agent_id}",
            browser=browser,
            max_history_items=75
        )
        print("Running a browser agent!") # TODO
        history = await browser_agent.run(max_steps=self._steps_per_work_cycle)

        try:
            agent_output = history.model_outputs()
            output_str = ""
            for i, output in enumerate(agent_output):
                if hasattr(output, "action"):
                    delattr(output, "action")  # Saves tokens + we do not need that much information

                if hasattr(output, "thinking"):
                    delattr(output, "thinking")
                output_str += f"\nStep {i}: {output}"

            self._outputs.append(output_str + "\n")
        except Exception as e:
            print(f"\n\n\n\n\nDebug (work history output generation for agent {self.agent_id}:\n{e}\n\n\n\n\n")

        await browser.kill()

    def discuss(self, current_conversation: str, task_history: str, current_files: str) -> Discuss:
        discuss_prompt = self._system_prompt + "\n---" + DISCUSS_PROMPT.substitute(
            # There is no built-in system prompt for structured output
            objective=self._project.objective,
            total_agents=self._project.total_agents,
            current_conversation=current_conversation,
            task_history=task_history,
            current_files=current_files,
            max_iterations=self._project.max_iterations,
            current_iteration=self._project.iteration_number,
            agent_id=self.agent_id
        )

        attempts = 0

        while attempts < 10:
            try:
                response = client.models.generate_content(
                    model=self._llm_name,
                    contents=discuss_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_json_schema=Discuss.model_json_schema(),
                        temperature=1.5,
                    )
                )

                return Discuss.model_validate(response.parsed)
            except Exception as e:
                attempts += 1
                print(f"(Attempt {attempts}) Discussion for Agent_{self.agent_id} failed with exception: {e}")
                sleep(5)

        raise Exception(f"Discussion for Agent_{self.agent_id} failed")