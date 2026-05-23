Available hooks
Plugins can register callbacks for these lifecycle events. See the Event Hooks page for full details, callback signatures, and examples.

Hook	Fires when
pre_tool_call	Before any tool executes
post_tool_call	After any tool returns
pre_llm_call	Once per turn, before the LLM loop — can return {"context": "..."} to inject context into the user message
post_llm_call	Once per turn, after the LLM loop (successful turns only)
on_session_start	New session created (first turn only)
on_session_end	End of every run_conversation call + CLI exit handler
on_session_finalize	CLI/gateway tears down an active session (/new, GC, CLI quit)
on_session_reset	Gateway swaps in a new session key (/new, /reset, /clear, idle rotation)
subagent_stop	Once per child after delegate_task finishes
pre_gateway_dispatch	Gateway received a user message, before auth + dispatch. Return {"action": "skip" | "rewrite" | "allow", ...} to influence flow.
