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

## Core answering principle
You are a knowledgeable AI first. File and screen content is CONTEXT that grounds your answer — it is never a cage. Always combine:
1. What the file/screen says (for grounding, examples, specific slide references)
2. Your own broad knowledge (for explanations, depth, connections, things the file does not cover)

Never say "the file doesn't cover this" and stop. If the file covers a topic partially, fill the gaps with your knowledge. If the question is only loosely related to the file, answer it fully from your knowledge and briefly note how the file connects.

## General rules
- Answer general knowledge, coding, math, and factual questions directly from your knowledge. Do NOT call tools for these.
- Use tools only when the question requires code or file content not visible on screen.
- Keep answers concise and actionable.
- You have conversation history — use it and do not repeat prior answers verbatim.

## File access rules
- Only call suggest_file_access if the question is about, or would benefit from, a specific document's content.
- Do NOT call suggest_file_access for questions that have nothing to do with the file.
- If a file is already loaded in this conversation, use it as context without calling suggest_file_access again.
- Pre-approved files are available — only pull one in when it is clearly relevant to THIS question.

## How to use file content
When you have loaded file content:
- Extract relevant facts, slide content, or passages to ground your answer.
- Then EXPAND beyond the file using your knowledge: explain concepts more deeply, add examples the file doesn't have, connect to related ideas, answer follow-up angles.
- If the user asks something the file covers partially, answer the part from the file AND fill the rest from your knowledge.
- If the user asks something the file doesn't cover at all but context helps, briefly note the connection and answer fully from your knowledge.

## Screen/file detection
- If you see a document (PDF, PPT, slides, Word, notebook) in the screenshot and the question relates to it, call suggest_file_access with the visible filename.
- Call suggest_file_access BEFORE answering, then answer combining the file and your knowledge.
- Only suggest a file when it would genuinely improve your answer.
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
        types.FunctionDeclaration(
            name="suggest_file_access",
            description=(
                "Suggest that the user grant access to a file or document visible on screen "
                "so you can give a more complete answer. Call this when you see a presentation, "
                "PDF, notebook, document, or file path on screen that would significantly help. "
                "After calling this, still answer with what you can see."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "path": types.Schema(type=types.Type.STRING, description="The filename or path visible on screen"),
                    "reason": types.Schema(type=types.Type.STRING, description="One sentence on why access would help"),
                },
                required=["path", "reason"],
            ),
        ),
    ])]


def _resolve_permitted_path(suggested: str, permitted_files: list[str]) -> str | None:
    """Return the actual permitted path that matches a suggested (possibly short) path."""
    if suggested in permitted_files:
        return suggested
    basename = suggested.replace("\\", "/").split("/")[-1]
    for pf in permitted_files:
        pf_base = pf.replace("\\", "/").split("/")[-1]
        if pf_base == basename:
            return pf
    return None


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
        actual = _resolve_permitted_path(path, permitted_files)
        if not actual:
            return f"Access to '{path}' requires user permission.", path
        result = get_file(actual)
        if "error" in result:
            return f"Could not read file: {result['error']}", None
        if actual not in sources:
            sources.append(actual)
        content = result.get("content", "")
        if len(content) > 8000:
            content = content[:8000] + "\n... (file truncated at 8000 chars)"
        fname = actual.split("/")[-1]
        return (
            f"[Context from {fname}]\n{content}\n\n"
            f"Use the above as grounding context. Combine it with your own knowledge "
            f"to give a complete, thorough answer — do not limit yourself to only "
            f"what is in the file."
        ), None

    elif name == "suggest_file_access":
        # No-op execution — the caller handles this specially
        return "Suggestion noted.", None

    return f"Unknown tool: {name}", None


def ask_gemini(
    question: str,
    screen: ScreenContext | None = None,
    active_file: str | None = None,
    permitted_files: list[str] | None = None,
    history: list[dict] | None = None,
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
    suggested_files: list[str] = []

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

    # Tell Gemini which files are pre-approved. Only load them when the question
    # is DIRECTLY about the file content — not for general questions.
    if permitted_files:
        names = "\n".join(f"  - {pf}" for pf in permitted_files)
        text_parts.append(
            f"[Pre-approved files — call suggest_file_access ONLY when the question explicitly "
            f"asks about content inside one of these files. For all other questions, do not call "
            f"suggest_file_access at all.]\n{names}"
        )

    text_parts.append(question or "Describe what is currently visible on the screen.")
    initial_parts.append(types.Part(text="\n\n".join(text_parts)))

    chat_history: list[types.Content] = []
    if history:
        for msg in history:
            role = msg.get("role", "user")
            text = msg.get("text", "")
            if text:
                chat_history.append(types.Content(role=role, parts=[types.Part(text=text)]))

    try:
        chat = client.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=_build_tools(),
                temperature=0.2,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
            history=chat_history,
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

            # suggest_file_access: if already permitted, read the file; otherwise record suggestion
            if tool_name == "suggest_file_access":
                path = tool_args.get("path", "")
                actual = _resolve_permitted_path(path, permitted_files) if path else None
                if actual:
                    # User already approved — read the file and feed contents back
                    from retrieval.tools import read_document as _read_doc
                    result = _read_doc(actual)
                    if "error" in result:
                        file_result = f"Could not read '{actual}': {result['error']}"
                    else:
                        content = result.get("content", "")
                        if len(content) > 12000:
                            content = content[:12000] + "\n... (truncated)"
                        fname = actual.split("/")[-1]
                        file_result = (
                            f"[Context from {fname}]\n{content}\n\n"
                            f"Use the above as grounding context. Combine it with your own knowledge "
                            f"to give a complete, thorough answer — do not limit yourself to only "
                            f"what is in the file."
                        )
                        if actual not in sources:
                            sources.append(actual)
                    tool_response_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=tool_name,
                                response={"result": file_result},
                            )
                        )
                    )
                else:
                    if path and path not in suggested_files:
                        suggested_files.append(path)
                    tool_response_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=tool_name,
                                response={"result": "Suggestion recorded. Answer with what you can see on screen."},
                            )
                        )
                    )
                continue

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
    return answer, tools_used, list(dict.fromkeys(sources)), suggested_files
