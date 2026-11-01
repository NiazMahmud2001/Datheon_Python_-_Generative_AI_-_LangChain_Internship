

import os, sys, ast, operator
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from langchain_community.tools import DuckDuckGoSearchRun

from dotenv import load_dotenv
load_dotenv()



# ================== Now Desing some Tools =========================
# tavily search tool
tool_search_int = TavilySearch(
    max_results=15,
    topic="general",
)




# File reader tool
@tool
def read_file(file_name: str) -> str:
    """Read a local text file from the files folder. Pass only the file name, e.g. 'notes.txt'."""
    # only file_storage/ is readable, so .env and the source code stay private
    folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "file_storage")
    file_path = os.path.abspath(os.path.join(folder_path , file_name))

    if not os.path.normcase(file_path).startswith(os.path.normcase(folder_path) + os.sep):   # "../../secret" ঠেকাও
        return "Error: access outside the files folder is not allowed"
    if not os.path.isfile(file_path):
        return f"Error: '{file_name}' not found. Available: {os.listdir(folder_path)}"

    
    with open(file_path, encoding="utf-8", errors="ignore") as f:
        return f.read(100000)





# calc tool
_CALC_OPS = {ast.Add: operator.add, 
        ast.Sub: operator.sub, 
        ast.Mult: operator.mul,
        ast.Div: operator.truediv, 
        ast.Pow: operator.pow, 
        ast.Mod: operator.mod,
        ast.USub: operator.neg, 
        ast.UAdd: operator.pos}


def _eval_ops(node): 
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): 
        return node.value
    
    if isinstance(node, ast.BinOp) and type(node.op) in _CALC_OPS: 
        return _CALC_OPS[type(node.op)](_eval_ops(node.left), _eval_ops(node.right))
    
    if isinstance(node, ast.UnaryOp) and type(node.op) in _CALC_OPS:
        return _CALC_OPS[type(node.op)](_eval_ops(node.operand))

    raise ValueError("Only numbers and + - * / ** % are allowed")



@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression, e.g. '(25 * 4) / 3 + 2**5'."""
    try:
        return str(_eval_ops(ast.parse(expression, mode="eval").body))
    except Exception as e:
        return f"Error: {e}"
