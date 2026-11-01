import os, sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from langchain_core.messages import AIMessage, ToolMessage
from main_for_graph import run_agent


import uuid
import gradio as gr

def respond(message, history, session_id):
    return run_agent(message, thread_id=session_id)


with gr.Blocks() as demo:
    session_id = gr.State(lambda: str(uuid.uuid4()))
    gr.ChatInterface(respond, additional_inputs=[session_id])

demo.launch(share=False)




























