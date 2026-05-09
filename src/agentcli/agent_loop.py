import json

from agentcli.tools import grep_text, read_file, save_note, search_files


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

    def _execute_tool(self, tool_name: str, arguments: dict[str, object]) -> object:
        if tool_name == "search_files":
            return search_files(self.runtime.repo_root, str(arguments["pattern"]))
        if tool_name == "grep_text":
            return grep_text(self.runtime.repo_root, str(arguments["needle"]))
        if tool_name == "read_file":
            path = self.runtime.repo_root / str(arguments["path"])
            start = int(arguments.get("start", 1))
            end = int(arguments.get("end", 80))
            return read_file(path, start=start, end=end)
        if tool_name == "save_note":
            output_dir = self.runtime.repo_root / "notes"
            return str(save_note(output_dir, str(arguments["slug"]), str(arguments["content"])))
        raise ValueError(f"Unknown tool: {tool_name}")

    def run(self, question: str) -> str:
        messages: list[dict[str, object]] = [
            {"role": "system", "content": self.runtime.system_prompt},
            {"role": "user", "content": question},
        ]
        for _ in range(6):
            response = self.adapter.respond(messages, self._tool_defs())
            if response["type"] == "final":
                return str(response["content"])
            if response["type"] != "tool_call":
                raise ValueError(f"Unsupported response type: {response['type']}")
            result = self._execute_tool(str(response["tool_name"]), dict(response["arguments"]))
            tool_call_id = str(response.get("tool_call_id", f"call_{_}"))
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
                                "name": str(response["tool_name"]),
                                "arguments": json.dumps(response["arguments"]),
                            },
                        }
                    ],
                },
            )
            messages.append(dict(assistant_message))
            content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
            messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})
        raise RuntimeError("Agent loop exceeded maximum step count")
