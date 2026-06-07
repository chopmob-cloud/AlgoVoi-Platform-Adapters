"""
AlgoVoi LangChain Adapter — Deployment Examples
================================================
Three usage patterns:
  1. Flask server-side gate (ChatOpenAI default)
  2. FastAPI server-side gate
  3. LangChain agent with AlgoVoiPaymentTool

Install:
    pip install langchain-core langchain-openai flask fastapi uvicorn
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mpp-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ap2-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "openai"))

from langchain_algovoi import AlgoVoiLangChain

gate = AlgoVoiLangChain(
    openai_key        = os.environ["OPENAI_KEY"],
    algovoi_key       = os.environ["ALGOVOI_KEY"],
    tenant_id         = os.environ["TENANT_ID"],
    payout_address    = os.environ["PAYOUT_ADDRESS"],
    protocol          = "mpp",              # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet", # "voi-mainnet" | "hedera-mainnet" | "stellar-mainnet"
    amount_microunits = 10000,              # 0.01 USDC per call
    model             = "gpt-4o",
)


# ── 1. Flask ──────────────────────────────────────────────────────────────────

def run_flask():
    from flask import Flask, request, jsonify, Response

    app = Flask(__name__)

    @app.route("/ai/chat", methods=["POST"])
    def chat():
        body   = request.get_json(silent=True) or {}
        result = gate.check(dict(request.headers), body)
        if result.requires_payment:
            flask_body, status, headers = result.as_flask_response()
            return Response(flask_body, status=status, headers=headers,
                            mimetype="application/json")
        return jsonify({"content": gate.complete(body.get("messages", []))})

    # Or use the convenience wrapper:
    @app.route("/ai/chat-simple", methods=["POST"])
    def chat_simple():
        return gate.flask_guard()

    # Custom LangChain chain example (LCEL pipe):
    @app.route("/ai/chain", methods=["POST"])
    def chain_endpoint():
        body   = request.get_json(silent=True) or {}
        result = gate.check(dict(request.headers), body)
        if result.requires_payment:
            flask_body, status, headers = result.as_flask_response()
            return Response(flask_body, status=status, headers=headers,
                            mimetype="application/json")

        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
        from langchain_core.output_parsers import StrOutputParser

        chain  = (
            ChatPromptTemplate.from_template("Answer the question: {question}")
            | ChatOpenAI(model="gpt-4o", api_key=os.environ["OPENAI_KEY"])
            | StrOutputParser()
        )
        output = gate.invoke_chain(chain, {"question": body.get("question", "")})
        return jsonify({"answer": output})

    app.run(host="0.0.0.0", port=8000, debug=False)


# ── 2. FastAPI ────────────────────────────────────────────────────────────────

def run_fastapi():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, Response
    import uvicorn

    app = FastAPI(title="AlgoVoi LangChain API")

    @app.post("/ai/chat")
    async def chat(req: Request):
        body   = await req.json()
        result = gate.check(dict(req.headers), body)
        if result.requires_payment:
            status_str, headers, body_bytes = result.as_wsgi_response()
            return Response(body_bytes, status_code=402, headers=dict(headers))
        content = gate.complete(body.get("messages", []))
        return {"content": content}

    uvicorn.run(app, host="0.0.0.0", port=8000)


# ── 3. LangChain agent with AlgoVoiPaymentTool ────────────────────────────────

def run_agent_example():
    """
    Drop AlgoVoiPaymentTool into any LangChain ReAct agent.
    The agent can use the tool to access payment-gated resources.
    """
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate

    # Protected resource the agent can access after payment
    def my_protected_resource(query: str) -> str:
        return f"Premium answer to '{query}': The answer is 42."

    tool = gate.as_tool(
        resource_fn      = my_protected_resource,
        tool_name        = "premium_knowledge_base",
        tool_description = (
            "Query the premium AlgoVoi knowledge base. Requires payment proof. "
            "Input: JSON with 'query' and optional 'payment_proof' fields."
        ),
    )

    llm = ChatOpenAI(model="gpt-4o", api_key=os.environ["OPENAI_KEY"])

    # Example: use with create_react_agent
    try:
        from langchain.agents import create_react_agent, AgentExecutor
        from langchain_core.prompts import PromptTemplate

        prompt = PromptTemplate.from_template(
            "You are a helpful assistant. Use the available tools to answer questions.\n"
            "Question: {input}\n"
            "Thought: {agent_scratchpad}"
        )
        agent    = create_react_agent(llm, [tool], prompt)
        executor = AgentExecutor(agent=agent, tools=[tool], verbose=True)
        result   = executor.invoke({"input": "Access the premium knowledge base and answer: what is 6x7?"})
        print("Agent result:", result)
    except ImportError:
        # Minimal example without full agent executor
        import json
        tool_input = json.dumps({
            "query":         "What is 6 times 7?",
            "payment_proof": "REPLACE_WITH_REAL_PROOF",
        })
        print("Tool output:", tool._run(tool_input))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "flask"
    if mode == "fastapi":
        run_fastapi()
    elif mode == "agent":
        run_agent_example()
    else:
        run_flask()
