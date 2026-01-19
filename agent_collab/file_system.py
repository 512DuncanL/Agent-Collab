from os.path import isfile
from pathlib import Path

from typing import ClassVar

import pypdf

class FileSystem:
    _agent_id: int
    _project_dir: Path

    _readable_file_types: ClassVar[list[str]] = ["pdf"]
    _writeable_file_types: ClassVar[list[str]] = ["txt", "text", "log", "readme", "md", "markdown", "rst", "adoc", "tex", "latex", "rtf", "html", "htm", "xhtml", "css", "scss", "sass", "less", "svg", "xml", "xsl", "xslt", "json", "yaml", "yml", "toml", "ini", "cfg", "conf", "config", "env", "properties", "csv", "tsv", "plist", "py", "pyw", "pyi", "pyx", "pxd", "ipynb", "js", "mjs", "cjs", "jsx", "ts", "tsx", "mts", "cts", "java", "kt", "kts", "scala", "groovy", "gradle", "c", "h", "cpp", "cc", "cxx", "hpp", "hxx", "cs", "m", "mm", "rs", "go", "zig", "nim", "v", "d", "hs", "lhs", "ml", "mli", "fs", "fsi", "fsx", "clj", "cljs", "cljc", "edn", "ex", "exs", "erl", "hrl", "elm", "rb", "rake", "gemspec", "php", "pl", "pm", "lua", "tcl", "r", "rmd", "sh", "bash", "zsh", "fish", "ps1", "psm1", "bat", "cmd", "dockerfile", "containerfile", "vagrantfile", "jenkinsfile", "sql", "ddl", "dml", "plsql", "psql", "mysql", "sqlite", "graphql", "make", "makefile", "cmake", "mk", "rake", "sbt", "maven", "bazel", "buck", "asm", "s", "nasm", "masm", "swift", "dart", "pas", "pp", "vb", "vbs", "bas", "awk", "sed", "lisp", "scm", "rkt", "jl", "mat", "f", "f90", "f95", "for", "cob", "cobol", "erb", "ejs", "j2", "jinja", "jinja2", "hbs", "mustache", "liquid", "twig", "pug", "jade", "gitignore", "gitattributes", "gitmodules", "hgignore", "npmignore", "dockerignore", "editorconfig", "prettierrc", "eslintrc", "babelrc", "nvmrc", "lock", "pid", "diff", "patch", "po", "pot", "srt", "vtt", "ics"]

    def __init__(self, agent_id: int, project_dir: Path):
        self._agent_id = agent_id
        self._project_dir = project_dir

    def _get_path(self, file_system: str) -> Path:
        if file_system == "private":
            return self._project_dir / f"file_system_{self._agent_id}"
        elif file_system == "collab":
            return self._project_dir / "file_system_collab"
        else:
            return self._project_dir / "file_system_output"

    def read_file(self, filename: str, file_system: str) -> str:
        assert file_system in ["private", "collab", "output"], f"{file_system} is not a supported file system"

        path = self._get_path(file_system=file_system)

        if not filename:
            return "Error: File name was not provided."

        if len(filename.split(".")) == 1 or filename.split(".")[-1] not in FileSystem._readable_file_types + FileSystem._writeable_file_types:
            return f"Error: Invalid file extension."

        if not isfile(path / filename):
            return f"Error: File {filename} was not found."

        extension = filename.split(".")[-1]

        if extension in FileSystem._writeable_file_types:
            with open(path / filename, "r", encoding='utf-8') as f:
                contents = f.read()

            return f'Successfully read from {file_system} file {filename}.\n<content>\n{contents}\n</content>'
        elif extension == "pdf":
            reader = pypdf.PdfReader(path / filename)
            num_pages = len(reader.pages)
            MAX_PDF_PAGES = 15
            extra_pages = num_pages - MAX_PDF_PAGES
            extracted_text = ''

            for page in reader.pages[:MAX_PDF_PAGES]:
                extracted_text += page.extract_text()

            extra_pages_text = f'{extra_pages} more pages...' if extra_pages > 0 else ''

            return f'Successfully read from {file_system} file {filename}.\n<content>\n{extracted_text}\n{extra_pages_text}</content>'
        else:
            return f"Error: File type {extension} was not implemented."

    def write_file(self, filename: str, contents: str, file_system: str) -> str:
        assert file_system in ["private", "collab", "output"], f"{file_system} is not a supported file system"

        path = self._get_path(file_system=file_system)

        if len(filename.split(".")) == 1 or filename.split(".")[-1] not in FileSystem._writeable_file_types:
            return f"Error: Invalid file extension."

        with open(path / filename, 'w', encoding='utf-8') as f:
            f.write(contents)

        return f'Successfully wrote to {file_system} file {filename}'

    def edit_file(self, filename: str, old_str: str, new_str: str, file_system: str) -> str:
        assert file_system in ["private", "collab", "output"], f"{file_system} is not a supported file system"

        path = self._get_path(file_system=file_system)

        if not filename:
            return "Error: File name was not provided."

        if len(filename.split(".")) == 1 or filename.split(".")[-1] not in FileSystem._writeable_file_types:
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

    def create_folder(self, folder_name: str, file_system: str) -> str:
        assert file_system in ["private", "collab", "output"], f"{file_system} is not a supported file system"

        if not folder_name:
            return "Error: Folder name was not provided."

        path = self._get_path(file_system=file_system) / folder_name

        if path.exists():
            return f"Error: Folder {folder_name} already exists."

        path.mkdir()

        return f"Successfully created {file_system} folder {folder_name}"