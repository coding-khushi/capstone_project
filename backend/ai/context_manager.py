"""Phase 5 + 10 + 11: Gemini agent with function calling, context routing, and file permissions."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from google import genai
from google.genai import types

from screen.processor import ScreenContext

load_dotenv()

GEMINI_MODEL = "gemini-3.5-flash-lite"
MAX_TOOL_CALLS = 4

SYSTEM_PROMPT = """
You are Percept, an AI assistant embedded in the user's desktop.

You can see the user's screen through screenshots and help them understand what is happening.

You have tools to look up code in the user's indexed project:
- search_project: semantic search over the codebase
- find_definition: find where a symbol is defined
- find_references: find where a symbol is used
- get_file: read a full file (only when explicitly permitted by the user)

Rules:
- Use tools when the question requires code context beyond what is visible on screen.
- Use get_file only if you genuinely need the full file and the user has granted access.
- Keep answers concise and actionable.
- Do not pretend to see information that is not in the screenshot or tool results.
"""


def _build_tools() -> list:
    return [types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="search_project",
            description="Semantic search over the indexed codebase. Use for general questions about how code works.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(type=types.Type.STRING, description="Natural language search query"),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="find_definition",
            description="Find where a function, class, or variable is defined in the project.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "symbol": types.Schema(type=types.Type.STRING, description="Symbol name to look up"),
                },
                required=["symbol"],
            ),
        ),
        types.FunctionDeclaration(
            name="find_references",
            description="Find all places in the codebase where a symbol is used.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "symbol": types.Schema(type=types.Type.STRING, description="Symbol name"),
                },
                required=["symbol"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_file",
            description="Read the full contents of a file. Only call this when the user has granted permission.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "path": types.Schema(type=types.Type.STRING, description="File path relative to project root"),
                },
                required=["path"],
            ),
        ),
    ])]


def _execute_tool(
    name: str,
    args: dict,
    permitted_files: list[str],
    sources: list[str],
) -> tuple[str, str | None]:
    """Execute a retrieval tool. Returns (result_text, permission_needed_path or None)."""
    from retrieval.tools import search_project, find_definition, find_references, get_file

    if name == "search_project":
        results = search_project(args.get("query", ""), top_k=4)
        if not results:
            return "No relevant code found in the indexed project.", None
        lines = []
        for r in results:
            if r["file"] not in sources:
                sources.append(r["file"])
            lines.append(
                f"// {r['file']} (lines {r.get('line_start', '?')}-{r.get('line_end', '?')})\n{r['text']}"
            )
        return "\n\n".join(lines), None

    elif name == "find_definition":
        result = find_definition(args.get("symbol", ""))
        if not result:
            return f"No definition found for '{args.get('symbol')}'.", None
        if result["file"] not in sources:
            sources.append(result["file"])
        return (
            f"'{args.get('symbol')}' is defined in {result['file']} "
            f"at line {result['line_start']} ({result['kind']})"
        ), None

    elif name == "find_references":
        from retrieval.tools import find_references as _find_refs
        results = _find_refs(args.get("symbol", ""))
        if not results:
            return f"No references found for '{args.get('symbol')}'.", None
        lines = [f"{r['file']}:{r['line']} — {r['text']}" for r in results[:8]]
        return "\n".join(lines), None

    elif name == "get_file":
        path = args.get("path", "")
        if path not in permitted_files:
            return f"Access to '{path}' requires user permission.", path
        result = get_file(path)
        if "error" in result:
            return f"Could not read file: {result['error']}", None
        if path not in sources:
            sources.append(path)
        content = result.get("content", "")
        if len(content) > 8000:
            content = content[:8000] + "\n... (file truncated at 8000 chars)"
        return f"Contents of {path}:\n{content}", None

    return f"Unknown tool: {name}", None


def ask_gemini(
    question: str,
    screen: ScreenContext | None = None,
    active_file: str | None = None,
    permitted_files: list[str] | None = None,
) -> tuple[str, list[str], list[str], list[str]]:
    """Run the Percept agent loop.

    Returns (answer, tools_used, sources, permission_required).
    permission_required is non-empty when the agent needs file access before it can answer.
    """
    if permitted_files is None:
        permitted_files = []

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return (
            "GOOGLE_API_KEY is not set. Add it to backend/.env and restart the server.",
            [], [], [],
        )

    client = genai.Client(api_key=api_key)
    tools_used: list[str] = []
    sources: list[str] = []
    permission_required: list[str] = []

    # Build the initial user message parts
    initial_parts: list = []

    if screen and screen.raw_screenshot_b64:
        tools_used.append("screenshot")
        try:
            image_bytes = base64.b64decode(screen.raw_screenshot_b64)
            initial_parts.append(
                types.Part.from_bytes(data=image_bytes, mime_type=screen.media_type)
            )
        except Exception as exc:
            return f"Could not process screenshot: {exc}", [], [], []

    text_parts: list[str] = []
    if active_file:
        text_parts.append(f"Active file: {active_file}")
    text_parts.append(question or "Describe what is currently visible on the screen.")
    initial_parts.append(types.Part.from_text("\n\n".join(text_parts)))

    try:
        chat = client.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=_build_tools(),
                temperature=0.2,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        response = chat.send_message(initial_parts)
    except Exception as exc:
        return f"Gemini API error: {exc}", tools_used, sources, []

    # Agent loop — up to MAX_TOOL_CALLS iterations
    for _ in range(MAX_TOOL_CALLS):
        # Collect function calls from the response
        function_calls = []
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    function_calls.append(part.function_call)

        if not function_calls:
            break

        # Execute each tool and collect responses
        tool_response_parts: list = []
        for fc in function_calls:
            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}

            if tool_name not in tools_used:
                tools_used.append(tool_name)

            result_text, perm_needed = _execute_tool(
                tool_name, tool_args, permitted_files, sources
            )

            if perm_needed and perm_needed not in permission_required:
                permission_required.append(perm_needed)

            tool_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=tool_name,
                        response={"result": result_text},
                    )
                )
            )

        # If any file permissions are needed, stop and ask the user
        if permission_required:
            return (
                "__permission_required__",
                tools_used,
                sources,
                permission_required,
            )

        try:
            response = chat.send_message(tool_response_parts)
        except Exception as exc:
            return f"Gemini API error during tool execution: {exc}", tools_used, sources, []

    answer = response.text or "I couldn't generate a response."
    return answer, tools_used, list(dict.fromkeys(sources)), []
