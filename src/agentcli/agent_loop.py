import json
from uuid import uuid4

from agentcli.analysis import parse_analysis_result, trace_python_flow
from agentcli.analysis.symbols import find_definitions, find_references, inspect_tests, trace_cli_command
from agentcli.engine.events import EventSink, NullEventSink
from agentcli.session import AnalysisSession
from agentcli.tools import grep_text, list_directory, read_file, read_multiple_files, search_files


class AgentLoop:
    def __init__(
        self,
        runtime,
        adapter,
        progress_callback=None,
        event_sink: EventSink | None = None,
        run_id: str | None = None,
    ) -> None:
        self.runtime = runtime
        self.adapter = adapter
        self.progress_callback = progress_callback
        self.event_sink = event_sink or NullEventSink()
        self.run_id = run_id

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
            if tool_name == "trace_flow":
                return trace_python_flow(
                    self.runtime.repo_root,
                    str(arguments.get("symbol", "")),
                    path=str(arguments["path"]) if "path" in arguments else None,
                )
            if tool_name == "find_references":
                return find_references(
                    self.runtime.repo_root,
                    str(arguments.get("symbol", "")),
                    path=str(arguments["path"]) if "path" in arguments else None,
                )
            if tool_name == "find_definitions":
                return find_definitions(
                    self.runtime.repo_root,
                    str(arguments.get("symbol", "")),
                    path=str(arguments["path"]) if "path" in arguments else None,
                )
            if tool_name == "trace_cli_command":
                return trace_cli_command(
                    self.runtime.repo_root,
                    str(arguments.get("command", "")),
                )
            if tool_name == "inspect_tests":
                return inspect_tests(self.runtime.repo_root)
            return {"error": f"Unknown tool: {tool_name}", "kind": "unknown_tool"}
        except Exception as exc:
            return {"error": f"Tool '{tool_name}' failed: {exc}", "kind": "tool_exception"}

    def _emit(self, run_id: str, event_type: str, **payload: object) -> None:
        self.event_sink.emit(event_type, run_id=run_id, **payload)

    @staticmethod
    def _line_range_from_content(content: str) -> tuple[int | None, int | None]:
        line_numbers: list[int] = []
        for line in content.splitlines():
            prefix = line.split("\t", 1)[0].strip()
            if prefix.isdigit():
                line_numbers.append(int(prefix))
        if not line_numbers:
            return None, None
        return line_numbers[0], line_numbers[-1]

    def _emit_tool_result_events(
        self,
        run_id: str,
        tool_name: str,
        arguments: dict[str, object],
        result: dict[str, object],
    ) -> None:
        if result.get("kind") == "file_content":
            path = str(result.get("path", arguments.get("path", "")))
            self._emit(run_id, "file_opened", path=path, tool_name=tool_name)
            start_line, end_line = self._line_range_from_content(str(result.get("content", "")))
            if start_line is not None and end_line is not None:
                self._emit(
                    run_id,
                    "line_range_read",
                    path=path,
                    start_line=start_line,
                    end_line=end_line,
                    tool_name=tool_name,
                )
        elif result.get("kind") == "multi_file_content":
            for file_result in result.get("files", []):
                if not isinstance(file_result, dict) or "content" not in file_result:
                    continue
                path = str(file_result.get("path", ""))
                self._emit(run_id, "file_opened", path=path, tool_name=tool_name)
                start_line, end_line = self._line_range_from_content(str(file_result.get("content", "")))
                if start_line is not None and end_line is not None:
                    self._emit(
                        run_id,
                        "line_range_read",
                        path=path,
                        start_line=start_line,
                        end_line=end_line,
                        tool_name=tool_name,
                    )

    def _emit_analysis_events(self, run_id: str, answer: str) -> None:
        result = parse_analysis_result(answer)
        if not (result.key_files or result.uncertainties or "##" in answer):
            return
        evidence_ids: list[str] = []
        for index, path in enumerate(result.key_files, start=1):
            evidence_id = f"ev_{index}"
            evidence_ids.append(evidence_id)
            self._emit(run_id, "evidence_added", id=evidence_id, path=path, source="answer")
        if result.conclusion:
            self._emit(
                run_id,
                "claim_added",
                id="claim_1",
                text=result.conclusion,
                confidence="medium",
                evidence_ids=evidence_ids,
            )
        for index, question in enumerate(result.uncertainties, start=1):
            self._emit(run_id, "open_question_added", id=f"oq_{index}", text=question)

    def _run_with_messages(self, messages: list[dict[str, object]], question: str = "") -> str:
        consecutive_errors = 0
        run_id = self.run_id or uuid4().hex

        self._emit(run_id, "run_started", question=question, max_steps=self.runtime.max_steps)
        self._emit(
            run_id,
            "project_map_ready",
            summary=self.runtime.project_map_summary,
        )
        self._emit(
            run_id,
            "reading_plan_created",
            steps=[
                "Review the project map",
                "Use tools to gather source evidence",
                "Answer with concrete files, uncertainties, and next steps",
            ],
        )

        for step in range(self.runtime.max_steps):
            response = self.adapter.respond(messages, self._tool_defs())

            if response["type"] == "final":
                answer = str(response["content"])
                messages.append({"role": "assistant", "content": answer})
                self._emit_analysis_events(run_id, answer)
                self._emit(run_id, "answer_final", answer=answer)
                self._emit(run_id, "run_finished", status="finished")
                return answer

            if response["type"] != "tool_call":
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    messages.append({
                        "role": "user",
                        "content": "Too many unexpected responses. Provide your best final answer now based on what you've seen.",
                    })
                    response = self.adapter.respond(messages, [])
                    if response["type"] == "final":
                        answer = str(response["content"])
                        messages.append({"role": "assistant", "content": answer})
                        self._emit_analysis_events(run_id, answer)
                        self._emit(run_id, "answer_final", answer=answer)
                        self._emit(run_id, "run_finished", status="recovered_after_unexpected_responses")
                        return answer
                    self._emit(run_id, "run_finished", status="failed")
                    return "Agent failed to produce a final answer after repeated unexpected responses."
                messages.append({
                    "role": "user",
                    "content": f"Unexpected response type '{response['type']}'. Please make a tool call or provide your final answer.",
                })
                continue

            tool_name = str(response.get("tool_name", ""))
            arguments = dict(response.get("arguments", {}))
            self._emit(run_id, "tool_started", step=step + 1, tool_name=tool_name, arguments=arguments)
            result = self._execute_tool(tool_name, arguments)
            self._emit_tool_result_events(run_id, tool_name, arguments, result)
            self._emit(run_id, "tool_finished", step=step + 1, tool_name=tool_name, result=result)
            if self.progress_callback is not None:
                self.progress_callback(
                    {
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "result": result,
                    }
                )

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
                    answer = str(response["content"])
                    messages.append({"role": "assistant", "content": answer})
                    self._emit_analysis_events(run_id, answer)
                    self._emit(run_id, "answer_final", answer=answer)
                    self._emit(run_id, "run_finished", status="recovered_after_tool_errors")
                    return answer
                self._emit(run_id, "run_finished", status="failed")
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
            answer = str(response["content"])
            messages.append({"role": "assistant", "content": answer})
            self._emit_analysis_events(run_id, answer)
            self._emit(run_id, "answer_final", answer=answer)
            self._emit(run_id, "run_finished", status="budget_exhausted")
            return answer
        self._emit(run_id, "run_finished", status="failed")
        raise RuntimeError("Agent loop exceeded maximum step count and did not produce a final answer")

    def run(self, question: str) -> str:
        messages: list[dict[str, object]] = [
            {"role": "system", "content": self.runtime.system_prompt},
            {"role": "user", "content": question},
        ]
        return self._run_with_messages(messages, question=question)

    def run_turn(self, session: AnalysisSession, user_message: str) -> str:
        if session.messages:
            messages = [dict(message) for message in session.messages]
        else:
            messages = [{"role": "system", "content": self.runtime.system_prompt}]

        summary_index: int | None = None
        if session.turns:
            summary_index = len(messages)
            messages.append({"role": "system", "content": session.render_summary()})

        messages.append({"role": "user", "content": user_message})
        answer = self._run_with_messages(messages, question=user_message)
        result = parse_analysis_result(answer)
        session.record_turn(user_message, result)

        if summary_index is not None:
            messages = messages[:summary_index] + messages[summary_index + 1:]
        session.messages = messages
        return answer
