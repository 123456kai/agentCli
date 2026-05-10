import json

from agentcli.tools import grep_text, list_directory, read_file, read_multiple_files, search_files


class AgentLoop:
    def __init__(self, runtime, adapter) -> None:
        self.runtime = runtime
        self.adapter = adapter

    def _tool_defs(self) -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self.runtime.tools.values()
        ]

    def _execute_tool(self, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        try:
            if tool_name == "search_files":
                return search_files(
                    self.runtime.repo_root,
                    str(arguments.get("pattern", "")),
                    glob=str(arguments["glob"]) if "glob" in arguments else None,
                )
            if tool_name == "grep_text":
                return grep_text(
                    self.runtime.repo_root,
                    str(arguments.get("needle", "")),
                    path=str(arguments["path"]) if "path" in arguments else None,
                    glob=str(arguments["glob"]) if "glob" in arguments else None,
                    ignore_case=bool(arguments.get("ignore_case", False)),
                )
            if tool_name == "read_file":
                return read_file(
                    self.runtime.repo_root,
                    str(arguments.get("path", "")),
                    line_offset=int(arguments.get("line_offset", 1)),
                    n_lines=int(arguments.get("n_lines", self.runtime.read_max_lines)),
                )
            if tool_name == "list_directory":
                return list_directory(
                    self.runtime.repo_root,
                    str(arguments.get("path", "")),
                )
            if tool_name == "read_multiple_files":
                raw_paths = arguments.get("paths", [])
                if isinstance(raw_paths, str):
                    import json as _json
                    raw_paths = _json.loads(raw_paths)
                paths = [str(p) for p in raw_paths]
                return read_multiple_files(
                    self.runtime.repo_root,
                    paths,
                    line_offset=int(arguments.get("line_offset", 1)),
                )
            return {"error": f"Unknown tool: {tool_name}", "kind": "unknown_tool"}
        except Exception as exc:
            return {"error": f"Tool '{tool_name}' failed: {exc}", "kind": "tool_exception"}

    def run(self, question: str) -> str:
        messages: list[dict[str, object]] = [
            {"role": "system", "content": self.runtime.system_prompt},
            {"role": "user", "content": question},
        ]

        consecutive_errors = 0

        for step in range(self.runtime.max_steps):
            response = self.adapter.respond(messages, self._tool_defs())

            if response["type"] == "final":
                return str(response["content"])

            if response["type"] != "tool_call":
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    messages.append({
                        "role": "user",
                        "content": "Too many unexpected responses. Provide your best final answer now based on what you've seen.",
                    })
                    response = self.adapter.respond(messages, [])
                    if response["type"] == "final":
                        return str(response["content"])
                    return "Agent failed to produce a final answer after repeated unexpected responses."
                messages.append({
                    "role": "user",
                    "content": f"Unexpected response type '{response['type']}'. Please make a tool call or provide your final answer.",
                })
                continue

            tool_name = str(response.get("tool_name", ""))
            arguments = dict(response.get("arguments", {}))
            result = self._execute_tool(tool_name, arguments)

            if "error" in result:
                consecutive_errors += 1
            else:
                consecutive_errors = 0

            tool_call_id = str(response.get("tool_call_id", f"call_{step}"))
            assistant_message = response.get(
                "assistant_message",
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                },
            )
            messages.append(dict(assistant_message))
            content = json.dumps(result, ensure_ascii=False)
            messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})

            if consecutive_errors >= 3:
                messages.append({
                    "role": "user",
                    "content": (
                        "Several tool calls have returned errors. "
                        "Stop calling tools and provide the best final answer you can "
                        "from the evidence already gathered. Mention any uncertainty explicitly."
                    ),
                })
                response = self.adapter.respond(messages, [])
                if response["type"] == "final":
                    return str(response["content"])
                return "Agent failed to produce a final answer after repeated tool errors."

        # Budget exhausted
        messages.append({
            "role": "user",
            "content": (
                "The tool budget is exhausted. Stop calling tools and provide the best final answer "
                "you can from the evidence already gathered. Mention any uncertainty explicitly."
            ),
        })
        response = self.adapter.respond(messages, [])
        if response["type"] == "final":
            return str(response["content"])
        raise RuntimeError("Agent loop exceeded maximum step count and did not produce a final answer")
