from browser_use import Agent as BrowserAgent, ChatGoogle, Tools, Browser
from dotenv import load_dotenv
from google import genai
from google.genai import types
from os.path import isfile
from os import listdir
from prompts import AGENT_SYSTEM_PROMPT, AGENT_TRAITS, BRAINSTORM_PROMPT, DISCUSS_PROMPT
from reset_folders import reset_folders
from json_output import Brainstorm, Discuss
from time import sleep
import asyncio
import pypdf
import sys

reset_folders()

load_dotenv()

client = genai.Client()

TOTAL_AGENTS = 3

class Agent:
    _id: int
    agent_traits: str
    system_prompt: str
    tasks: list[str]
    outputs: list[str]
    llm_name: str
    steps_per_work_cycle: int

    def __init__(self, _id: int, agent_traits: str, llm_name: str, steps_per_work_cycle: int):
        self._id = _id
        self.agent_traits = agent_traits
        self.system_prompt = AGENT_SYSTEM_PROMPT.substitute(
            agent_id=self._id,
            total_agents=TOTAL_AGENTS,
            agent_traits=self.agent_traits
        )
        self.tasks = []
        self.outputs = []
        self.llm_name = llm_name
        self.steps_per_work_cycle = steps_per_work_cycle

    def add_task(self, task: str):
        self.tasks.append(task)

    def get_id(self):
        return self._id

    def get_task_history(self):
        return [self.tasks, self.outputs]

    def brainstorm(self, objective: str, current_conversation: str):
        brainstorm_prompt = self.system_prompt + "\n---" + BRAINSTORM_PROMPT.substitute( # There is no built-in system prompt for structured output
            objective=objective,
            total_agents=TOTAL_AGENTS,
            current_conversation=current_conversation,
            agent_id=self._id
        )

        attempts = 0

        while attempts < 10:
            try:
                response = client.models.generate_content(
                    model=self.llm_name,
                    contents=brainstorm_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_json_schema=Brainstorm.model_json_schema(),
                    )
                )

                return Brainstorm.model_validate(response.parsed)
            except Exception as e:
                attempts += 1
                print(f"(Attempt {attempts}) Brainstorm for Agent_{self._id} failed with exception: {e}")
                sleep(5)

        return None

    async def work(self):
        task = self.tasks[-1]

        tools = Tools(exclude_actions=['write_file', 'read_file', 'replace_file_str'])

        def read_file(filename: str, file_type: str) -> str:
            assert file_type in ["private", "collab", "output"], f"{file_type} is not a supported file type"

            path = f"./file_system_{self._id}" if file_type == "private" else "./file_system_collab" if file_type == "collab" else "./file_system_output"

            if not filename:
                return "Error: File name was not provided."

            if len(filename.split(".")) == 1 or filename.split(".")[-1] not in ["txt", "md", "csv", "json", "pdf"]:
                return f"Error: Invalid file extension."

            if not isfile(f"{path}/{filename}"):
                return f"Error: File {filename} was not found."

            extension = filename.split(".")[-1]

            if extension in ["txt", "md", "csv", "json"]:
                with open(f"{path}/{filename}", "r", encoding='utf-8') as f:
                    contents = f.read()

                return f'Successfully read from {file_type} file {filename}.\n<content>\n{contents}\n</content>'
            else:  # extension is pdf
                reader = pypdf.PdfReader(f"{path}/{filename}")
                num_pages = len(reader.pages)
                MAX_PDF_PAGES = 15
                extra_pages = num_pages - MAX_PDF_PAGES
                extracted_text = ''

                for page in reader.pages[:MAX_PDF_PAGES]:
                    extracted_text += page.extract_text()

                extra_pages_text = f'{extra_pages} more pages...' if extra_pages > 0 else ''

                return f'Successfully read from {file_type} file {filename}.\n<content>\n{extracted_text}\n{extra_pages_text}</content>'

        def write_file(filename: str, contents: str, file_type: str) -> str:
            assert file_type in ["private", "collab", "output"], f"{file_type} is not a supported file type"

            path = f"./file_system_{self._id}" if file_type == "private" else "./file_system_collab" if file_type == "collab" else "./file_system_output"

            if len(filename.split(".")) == 1 or filename.split(".")[-1] not in ["txt", "md", "csv", "json"]:
                return f"Error: Invalid file extension."

            with open(f"{path}/{filename}", 'w', encoding='utf-8') as f:
                f.write(contents)

            return f'Successfully wrote to {file_type} file {filename}'

        def replace_file_str(filename: str, old_str: str, new_str: str, file_type: str) -> str:
            assert file_type in ["private", "collab", "output"], f"{file_type} is not a supported file type"

            path = f"./file_system_{self._id}" if file_type == "private" else "./file_system_collab" if file_type == "collab" else "./file_system_output"

            if not filename:
                return "Error: File name was not provided."

            if len(filename.split(".")) == 1 or filename.split(".")[-1] not in ["txt", "md", "csv", "json"]:
                return f"Error: Invalid file extension."

            if not isfile(f"{path}/{filename}"):
                return f"Error: File {filename} was not found."

            if not old_str:
                return "Error: Cannot replace empty string. Please provide a non-empty string to replace."

            with open(f"{path}/{filename}", 'r', encoding='utf-8') as f:
                contents = f.read()

            contents = contents.replace(old_str, new_str)

            with open(f"{path}/{filename}", 'w', encoding='utf-8') as f:
                f.write(contents)

            return f'Successfully replaced all occurrences of "{old_str}" with "{new_str}" in {file_type} file {filename}'

        @tools.action(description='Read a private file named `filename`')
        def read_private_file(filename: str) -> str:
            return read_file(filename=filename, file_type="private")

        @tools.action(description='Write `contents` to a private file named `filename`. Overwrites previous file if it already exists.')
        def write_private_file(filename: str, contents: str) -> str:
            return write_file(filename=filename, contents=contents, file_type="private")

        @tools.action(description='Replace `old_str` with `new_str` in a private file named `file_name`')
        def replace_private_file_str(filename: str, old_str: str, new_str: str) -> str:
            return replace_file_str(filename=filename, old_str=old_str, new_str=new_str, file_type="private")

        @tools.action(description='Read a collaborative file named `filename`')
        def read_collab_file(filename: str) -> str:
            return read_file(filename=filename, file_type="collab")

        @tools.action(description='Write `contents` to a collaborative file named `filename`. Overwrites collaborative file if it already exists.')
        def write_collab_file(filename: str, contents: str) -> str:
            return write_file(filename=filename, contents=contents, file_type="collab")

        @tools.action(description='Replace `old_str` with `new_str` in a collaborative file named `file_name`')
        def replace_collab_file_str(filename: str, old_str: str, new_str: str) -> str:
            return replace_file_str(filename=filename, old_str=old_str, new_str=new_str, file_type="collab")

        @tools.action(description='Read a output file named `filename`')
        def read_output_file(filename: str) -> str:
            return read_file(filename=filename, file_type="output")

        @tools.action(description='Write `contents` to an output file named `filename`. Overwrites output file if it already exists.')
        def write_output_file(filename: str, contents: str) -> str:
            return write_file(filename=filename, contents=contents, file_type="output")

        @tools.action(description='Replace `old_str` with `new_str` in an output file named `file_name`')
        def replace_output_file_str(filename: str, old_str: str, new_str: str) -> str:
            return replace_file_str(filename=filename, old_str=old_str, new_str=new_str, file_type="output")

        browser = Browser(
            downloads_path=f"./file_system_{self._id}",
            window_size={'width': 1280, 'height': 800},
            user_data_dir=f'./agent-profile-{self._id}'
        )
        browser_llm = ChatGoogle(model=self.llm_name, temperature=0.6)
        browser_agent = BrowserAgent(
            task=task,
            llm=browser_llm, tools=tools,
            available_file_paths=[f"./file_system_{self._id}", "./file_system_collab", "./file_system_output"],
            file_system_path=f"./file_system_{self._id}",
            browser=browser,
            max_history_items=50
        )

        history = await browser_agent.run(max_steps=self.steps_per_work_cycle)

        try:
            agent_output = history.model_outputs()
            output_str = ""
            for i, output in enumerate(agent_output):
                if hasattr(output, "action"):
                    delattr(output, "action") # Saves tokens + we do not need that much information

                if hasattr(output, "thinking"):
                    delattr(output, "thinking")
                output_str += f"\nStep {i}: {output}"

            self.outputs.append(output_str + "\n")
        except Exception as e:
            print(f"\n\n\n\n\nDebug (work history output generation for agent {self._id}:\n{e}\n\n\n\n\n")
        #self.outputs.append(agent_output)

        await browser.kill()

        #return agent_output

    def discuss(self,
                objective: str,
                current_conversation: str,
                task_history: str,
                current_files: str,
                max_iterations: int,
                current_iteration: int):
        discuss_prompt = self.system_prompt + "\n---" + DISCUSS_PROMPT.substitute(
            # There is no built-in system prompt for structured output
            objective=objective,
            total_agents=TOTAL_AGENTS,
            current_conversation=current_conversation,
            task_history=task_history,
            current_files=current_files,
            max_iterations=max_iterations,
            current_iteration=current_iteration,
            agent_id=self._id
        )

        attempts = 0

        while attempts < 10:
            try:
                response = client.models.generate_content(
                    model=self.llm_name,
                    contents=discuss_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_json_schema=Discuss.model_json_schema(),
                    )
                )

                return Discuss.model_validate(response.parsed)
            except Exception as e:
                attempts += 1
                print(f"(Attempt {attempts}) Discussion for Agent_{self._id} failed with exception: {e}")
                sleep(5)

        return None

class Project:
    agents: list[Agent]
    objective: str
    conversations: list[str]
    max_iterations: int
    iteration_number: int

    def __init__(self, objective: str, max_iterations: int):
        self.agents = []
        self.objective = objective
        self.conversations = [""]
        self.max_iterations = max_iterations
        self.iteration_number = 1

    def add_agent(self, agent: Agent):
        self.agents.append(agent)

    def brainstorm(self):
        current_agent = 0
        votes = 0

        while True:
            brainstorm_result = self.agents[current_agent].brainstorm(
                objective=self.objective,
                current_conversation=self.conversations[-1]
            )

            if brainstorm_result is None:
                raise Exception(f"Brainstorming for Agent_{current_agent} failed")

            print("Debug (conversation): " + str(brainstorm_result)) # TODO

            self.conversations[-1] += f"{brainstorm_result.message_to_team}\nMy proposed subtask assignments: {brainstorm_result.subtask_assignments}\n---\n"
            subtask_assignments = brainstorm_result.subtask_assignments
            votes += brainstorm_result.vote
            current_agent = current_agent + 1 if current_agent < TOTAL_AGENTS - 1 else 0

            if votes >= TOTAL_AGENTS:
                for i, agent_name in enumerate(subtask_assignments):
                    if i >= TOTAL_AGENTS:
                        break # output sometimes contains non-agents

                    agent_id = int(agent_name[6:])
                    self.agents[agent_id].add_task(subtask_assignments[agent_name])

                    print("Debug (assigned tasks for agent {agent_id}):", agent_name, subtask_assignments[agent_name]) # TODO

                break

    def work(self):
        async def work_runner():
            work = [agent.work() for agent in self.agents]
            work_results = await asyncio.gather(*work, return_exceptions=True)

            return work_results

        completed_actions = asyncio.run(work_runner())

    def discuss(self):
        DISCUSSION_LIMIT = TOTAL_AGENTS * 8
        current_agent = 0
        discussion_votes = 0
        project_votes = 0
        rounds = 0

        full_agent_task_history = ""
        for agent in self.agents:
            executed_tasks, outputs = agent.get_task_history()
            assert len(executed_tasks) == len(outputs), f"agent {agent.get_id()}'s tasks: {len(executed_tasks), executed_tasks}, outputs: {len(outputs), outputs}" # Sanity check
            full_agent_task_history += f"Agent_{agent.get_id()}'s completed tasks and task outputs:\n"
            for i in range(len(executed_tasks)):
                full_agent_task_history += f"Description of task {i} of Agent_{agent.get_id()}: {executed_tasks[i]}\n\n"
            full_agent_task_history += f"\nActions completed for task {len(executed_tasks) - 1} of Agent_{agent.get_id()}: {outputs[len(executed_tasks) - 1]}\n---\n\n"
            # We add all previous task descriptions + actions for most recent task to context

        print("Debug (task history):\n" + full_agent_task_history) # TODO

        current_files = f"Output Files: {', '.join(listdir('./file_system_output'))}\nCollaborative Files: {', '.join(listdir('./file_system_collab'))}".replace(".gitkeep, ", "")
        for agent in self.agents:
            current_files += f"\nAgent {agent.get_id()}'s Private Files: " + ", ".join(listdir(f"./file_system_{agent.get_id()}"))

        print("Debug (files):\n" + current_files) # TODO

        while True:
            discuss_result = self.agents[current_agent].discuss(
                task_history=full_agent_task_history,
                current_files=current_files,
                objective=self.objective,
                current_conversation=self.conversations[-1],
                max_iterations=self.max_iterations,
                current_iteration=self.iteration_number
            )

            if discuss_result is None:
                raise Exception(f"Discussion for Agent_{current_agent} failed")

            print("Debug (conversation): " + str(discuss_result)) # TODO

            self.conversations[-1] += f"{discuss_result.message_to_team}\nMy proposed subtask assignments: {discuss_result.subtask_assignments}\n---\n"
            subtask_assignments = discuss_result.subtask_assignments
            discussion_votes = discussion_votes + discuss_result.end_discussion_vote if discuss_result.end_discussion_vote else 0
            project_votes = project_votes + discuss_result.complete_project_vote if discuss_result.complete_project_vote else 0 # Reset vote counter if an agent disagrees
            current_agent = current_agent + 1 if current_agent < TOTAL_AGENTS - 1 else 0

            if project_votes >= TOTAL_AGENTS:
                print(f"The project objective \"{self.objective}\" has been completed after {self.iteration_number - 1} iterations of work.")
                input("Press Enter to continue...")
                sys.exit(0)

            if discussion_votes >= TOTAL_AGENTS or rounds >= DISCUSSION_LIMIT:
                for i, agent_name in enumerate(subtask_assignments):
                    if i >= TOTAL_AGENTS:
                        break  # output sometimes contains non-agents

                    agent_id = int(agent_name[6:])
                    self.agents[agent_id].add_task(subtask_assignments[agent_name])

                    print("Debug (assigned tasks):", agent_name, subtask_assignments[agent_name])  # TODO

                break

            rounds += 1

    def execute(self):
        self.brainstorm()
        self.work()
        for _ in range(self.max_iterations - 1):
            self.iteration_number += 1
            self.discuss()
            self.work()

        print(f"The project objective \"{self.objective}\" has been completed after {self.iteration_number - 1} iterations of work.")
        input("Press Enter to continue...")
        sys.exit(0)

project = Project(
    objective="Conduct research on the effects of tobacco on children and create a full stack website on it using Flask as the backend. Keep the original file extension behind the `.txt` extension. No matter the file type, the extension should always end with `.txt`. For example, the main python file could be named `main.py.txt`.",
    max_iterations=6
)

for i in range(TOTAL_AGENTS):
    project.add_agent(Agent(
        _id=i,
        agent_traits=AGENT_TRAITS[i],
        llm_name="gemini-2.5-flash",
        steps_per_work_cycle=50
    ))

project.execute()