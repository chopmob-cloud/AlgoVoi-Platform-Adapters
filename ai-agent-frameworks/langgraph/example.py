"""
AlgoVoi LangGraph Adapter — Deployment Examples
================================================
Three usage patterns:
  1. Flask server-side gate (StateGraph)
  2. FastAPI server-side gate
  3. LangGraph agent with AlgoVoiPaymentTool via ToolNode

Install:
    pip install langgraph langchain-core langchain-openai flask fastapi uvicorn
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from langgraph_algovoi import AlgoVoiLangGraph

gate = AlgoVoiLangGraph(
    algovoi_key       = os.environ["ALGOVOI_KEY"],
    tenant_id         = os.environ["TENANT_ID"],
    payout_address    = os.environ["PAYOUT_ADDRESS"],
    protocol          = "mpp",              # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet", # "voi-mainnet" | "hedera-mainnet" | "stellar-mainnet"
    amount_microunits = 10000,              # 0.01 USDC per call
)


# ── Build a simple StateGraph ──────────────────────────────────────────────────

def _build_graph():
    """
    Compile a minimal LangGraph StateGraph for demo purposes.
    Replace with your actual agent graph.
    """
    from typing import TypedDict, Annotated
    from langgraph.graph import StateGraph, END
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import BaseMessage, HumanMessage
    import operator

    class AgentState(TypedDict):
        messages: Annotated[list[BaseMessage], operator.add]

    llm = ChatOpenAI(model="gpt-4o", api_key=os.environ["OPENAI_KEY"])

    def agent_node(state: AgentState) -> AgentState:
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.set_entry_point("agent")
    graph.add_edge("agent", END)
    return graph.compile()


# ── 1. Flask ──────────────────────────────────────────────────────────────────

def run_flask():
    from flask import Flask, request, jsonify, Response

    app    = Flask(__name__)
    graph  = _build_graph()

    # Pattern A: manual check + invoke
    @app.route("/agent/chat", methods=["POST"])
    def chat():
        body   = request.get_json(silent=True) or {}
        result = gate.check(dict(request.headers), body)
        if result.requires_payment:
            flask_body, status, headers = result.as_flask_response()
            return Response(flask_body, status=status, headers=headers,
                            mimetype="application/json")
        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content=m["content"]) for m in body.get("messages", [])]
        output   = gate.invoke_graph(graph, {"messages": messages})
        return jsonify({"messages": [m.content for m in output["messages"]]})

    # Pattern B: convenience flask_agent wrapper
    @app.route("/agent/simple", methods=["POST"])
    def simple():
        return gate.flask_agent(graph)

    # Pattern C: flask_guard for separate route logic
    @app.route("/agent/guarded", methods=["POST"])
    def guarded():
        guard = gate.flask_guard()
        if guard is not None:
            return guard           # 402
        body   = request.get_json(silent=True) or {}
        output = gate.invoke_graph(graph, {"messages": body.get("messages", [])})
        return jsonify(output)

    # Streaming endpoint
    @app.route("/agent/stream", methods=["POST"])
    def stream_endpoint():
        from flask import stream_with_context
        body   = request.get_json(silent=True) or {}
        result = gate.check(dict(request.headers), body)
        if result.requires_payment:
            flask_body, status, headers = result.as_flask_response()
            return Response(flask_body, status=status, headers=headers,
                            mimetype="application/json")

        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content=m["content"]) for m in body.get("messages", [])]

        def generate():
            import json
            for chunk in gate.stream_graph(graph, {"messages": messages},
                                           stream_mode="updates"):
                yield json.dumps(chunk) + "\n"

        return Response(stream_with_context(generate()), mimetype="application/x-ndjson")

    app.run(host="0.0.0.0", port=8000, debug=False)


# ── 2. FastAPI ────────────────────────────────────────────────────────────────

def run_fastapi():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, Response, StreamingResponse
    import uvicorn

    app   = FastAPI(title="AlgoVoi LangGraph API")
    graph = _build_graph()

    @app.post("/agent/chat")
    async def chat(req: Request):
        body   = await req.json()
        result = gate.check(dict(req.headers), body)
        if result.requires_payment:
            _, headers, body_bytes = result.as_wsgi_response()
            return Response(body_bytes, status_code=402, headers=dict(headers))
        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content=m["content"]) for m in body.get("messages", [])]
        output   = gate.invoke_graph(graph, {"messages": messages})
        return {"messages": [m.content for m in output["messages"]]}

    @app.post("/agent/stream")
    async def stream(req: Request):
        body   = await req.json()
        result = gate.check(dict(req.headers), body)
        if result.requires_payment:
            _, headers, body_bytes = result.as_wsgi_response()
            return Response(body_bytes, status_code=402, headers=dict(headers))

        from langchain_core.messages import HumanMessage
        import json
        messages = [HumanMessage(content=m["content"]) for m in body.get("messages", [])]

        async def generate():
            for chunk in gate.stream_graph(graph, {"messages": messages},
                                           stream_mode="updates"):
                yield json.dumps(chunk) + "\n"

        return StreamingResponse(generate(), media_type="application/x-ndjson")

    uvicorn.run(app, host="0.0.0.0", port=8000)


# ── 3. LangGraph agent with AlgoVoiPaymentTool + ToolNode ─────────────────────

def run_tool_node_example():
    """
    Drop AlgoVoiPaymentTool into a LangGraph ReAct agent via ToolNode.
    The agent pays for premium resource access on-chain before returning.
    """
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    # Protected resource behind the payment gate
    def my_kb(query: str) -> str:
        return f"Premium answer to '{query}': The Algorand network processes ~6000 TPS."

    # Build a ToolNode-compatible tool
    tool = gate.as_tool(
        resource_fn      = my_kb,
        tool_name        = "premium_knowledge_base",
        tool_description = (
            "Query the premium AlgoVoi knowledge base. Requires payment proof. "
            "Provide query (the question) and payment_proof (leave empty to receive challenge)."
        ),
    )

    llm   = ChatOpenAI(model="gpt-4o", api_key=os.environ["OPENAI_KEY"])
    agent = create_react_agent(llm, [tool])

    from langchain_core.messages import HumanMessage
    result = agent.invoke({
        "messages": [HumanMessage(content="What is the Algorand network TPS?")]
    })
    print("Agent result:", result["messages"][-1].content)


# ── 4. Custom StateGraph with ToolNode ────────────────────────────────────────

def run_custom_graph_example():
    """
    Use gate.tool_node() to embed the payment gate inside a custom StateGraph.
    """
    from typing import TypedDict, Annotated
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import ToolNode
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
    import operator

    class State(TypedDict):
        messages: Annotated[list[BaseMessage], operator.add]

    def my_kb(query: str) -> str:
        return f"Answer: 42 (query was: {query})"

    # gate.tool_node() returns a ready-to-use ToolNode
    payment_node = gate.tool_node(
        resource_fn  = my_kb,
        tool_name    = "premium_kb",
        tool_description = "Payment-gated knowledge base.",
    )

    llm = ChatOpenAI(model="gpt-4o", api_key=os.environ["OPENAI_KEY"])

    def should_use_tools(state: State) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    def agent_node(state: State) -> State:
        return {"messages": [lm.invoke(state["messages"])]}

    graph = StateGraph(State)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", payment_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_use_tools)
    graph.add_edge("tools", "agent")
    compiled = graph.compile()

    output = compiled.invoke({"messages": [HumanMessage(content="Look up the answer")]})
    print("Graph output:", output["messages"][-1].content)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "flask"
    if mode == "fastapi":
        run_fastapi()
    elif mode == "tool":
        run_tool_node_example()
    elif mode == "graph":
        run_custom_graph_example()
    else:
        run_flask()
