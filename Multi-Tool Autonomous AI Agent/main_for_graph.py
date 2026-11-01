

import os, sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from typing import Annotated
from pydantic import BaseModel, Field



from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage, AnyMessage
from langgraph.graph.message import add_messages


from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import InMemorySaver

from tools import tool_search_int , read_file, calculator

from dotenv import load_dotenv
load_dotenv()



MAX_TOOL_CALLS = int(os.getenv("MAX_TOOL_CALLS"))


# ================== get tools =========================
all_tools = [tool_search_int, calculator, read_file]


SYSTEM = SystemMessage(
    "You are a helpful agent. Before calling a tool, briefly explain your reasoning in one sentence. Use Tavily search for current facts, calculator for any math, read_file for local files."
)


llm = ChatOpenAI(
    model="nvidia/nemotron-3.5-lightning:free",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    temperature=0,
)
SYSTEM = SystemMessage(
    "You are a helpful agent. Before calling a tool, briefly explain your reasoning in one sentence. Use Tavily search for current facts, calculator for any math, read_file for local files."
)
llm_with_tools = llm.bind_tools(all_tools)





# ============== Now build LangGraph Loops and memory ==============
class AgentState(BaseModel):
    messages: Annotated[list[AnyMessage], add_messages] = Field(default_factory=list)  
    # add_messages -> it is a reducer .. it adds new message with the old ones ... it does not replaces
    tool_calls_count: int = Field(0, description="How many tools the agent has called in this run")



def agent_call_node(state: AgentState):
    response = llm_with_tools.invoke([SYSTEM] + state.messages)

    return {
        "messages": [response],
        "tool_calls_count": state.tool_calls_count + len(response.tool_calls),
    }



def tool_limit_node(state: AgentState):  # if tool limit touched then this part will be executed 
    last = state.messages[-1]
    skipped = [ToolMessage(content="Tool limit reached. This tool was not executed.", tool_call_id=tc["id"]) for tc in last.tool_calls]

    final = llm.invoke(
        [SYSTEM] + state.messages + skipped + [HumanMessage("Tool limit reached. Give your final answer now using only the information above. Say clearly which parts are missing.")]
    )

    return {"messages": skipped + [final]}




def route_after_calling_agent(state: AgentState):
    last_message = state.messages[-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        if state.tool_calls_count <= MAX_TOOL_CALLS:
            return "tools"
        return "tool_limit_node"
    return END



# ========== Build the graph ==========
workingAgent = StateGraph(AgentState)


workingAgent.add_node("agent_call_node", agent_call_node)
workingAgent.add_node("tools", ToolNode(all_tools))
workingAgent.add_node("tool_limit_node", tool_limit_node)


workingAgent.add_edge(START, "agent_call_node")

workingAgent.add_conditional_edges(
    "agent_call_node", 
    route_after_calling_agent, 
    ["tools", "tool_limit_node", END])

workingAgent.add_edge("tools", "agent_call_node")
workingAgent.add_edge("tool_limit_node", END)


agent_graph_with_mem = workingAgent.compile(checkpointer=InMemorySaver())









# ===================== Now build a funciton that will be called from Grdio UI =====================
def run_agent(question: str, thread_id: str = "cli"):# cli for gradio UI
    cfg = {
        "configurable": {"thread_id": thread_id}, 
        "recursion_limit": 25
    }
    steps = []

    for update in agent_graph_with_mem.stream({"messages": [("user", question)]}, cfg, stream_mode="updates"):
        # for building responsize ui : I will return node wise response in Gradio UI ... so steam with updates
         for node_output in update.values():
            for msg in node_output["messages"]:

                if isinstance(msg, AIMessage) and msg.tool_calls:
                    if msg.content:
                        steps.append(f"Thought: {msg.content}")
                    for tc in msg.tool_calls:
                        steps.append(f"Action: {tc['name']}({tc['args']})")

                elif isinstance(msg, ToolMessage):
                    steps.append(f"Observation: {str(msg.content)[:500]}")
                elif isinstance(msg, AIMessage):
                    steps.append(f"Final Answer: {msg.content}")
    return "\n\n".join(steps)





print(run_agent("What is the current population of UAE? Divide it by Each Emirates."))





