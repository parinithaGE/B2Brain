# B2B Documentation Assistant

This project is a readable, source-grounded Microsoft Dynamics 365 Commerce B2B documentation assistant.

## Architecture

- `main.py` contains the entire Streamlit frontend.
- `app/assistant.py` contains the terminal-style pipeline and prints its progress to the terminal.
- `app/utils/mcp.py` connects to the official GitHub MCP server over stdio.
- `app/utils/llm.py` connects to Ollama over HTTP.
- `app/skills/` contains the two Ollama skill prompts and their loader.
- `app/skills/question_analyzer.txt` is Ollama's question-understanding system prompt.
- `app/skills/answer_engine.txt` is Ollama's final-answer system prompt.
- No RAG/vector database is used.
- The pipeline searches all configured passes, ranks candidates, and fetches exactly one source file before generating the answer.
- The Streamlit frontend behaves like a chat conversation while leaving the backend pipeline unchanged.

## Setup

Create the environment:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create `.env`:

```powershell
copy .env.example .env
```

Edit `.env` and set:

- `GITHUB_PERSONAL_ACCESS_TOKEN`
- `MCP_EXE`
- `OLLAMA_URL`
- `OLLAMA_MODEL` if needed

The Ollama URL can be either the host URL or the full `/api/generate` URL.

## Verify

```powershell
python -m py_compile main.py app\assistant.py app\analyzer.py app\ranker.py app\question_analyzer.py app\startup.py app\skills\__init__.py app\utils\llm.py app\utils\mcp.py
```

Then:

```powershell
python -c "import main; print('MAIN IMPORT OK')"
```

## Run

```powershell
streamlit run main.py
```

The browser frontend appears at the URL printed by Streamlit, normally `http://localhost:8501`.

The browser UI is a chat interface: submit a question, see the answer, then ask another question. Previous turns remain visible.

The terminal continues to print the pipeline stages, including question understanding, all MCP search passes, the selected file, source analysis, and final answer.

## GitHub MCP

The application starts the GitHub MCP binary with the `stdio` subcommand and uses `search_code` and `get_file_contents`.

The GitHub MCP `search_code` call uses the tool's `query` argument. It does not use `q`.

The file fetch extracts the actual Markdown from the MCP `EmbeddedResource`. The status text such as `successfully downloaded text file (SHA: ...)` is not treated as the source content.

Do not run the MCP executable by itself as a normal command while testing the application; the application starts it as an MCP stdio server.

## Security

Never commit `.env`.

If a GitHub token has previously been exposed, revoke it and create a replacement token.
