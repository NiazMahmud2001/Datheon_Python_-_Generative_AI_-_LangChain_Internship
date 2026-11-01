import os
import pymupdf, docx, time , json
from datetime import date

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator, ValidationError
from typing import Optional

from langgraph.graph import END, START, StateGraph
from openrouter import OpenRouter

from prompt import SYSTEM_PROMPT, EXAMPLE_OUTPUT, USER_PROMPT, RETRY_PROMPT

from dotenv import load_dotenv
load_dotenv()


OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
MAX_RETRIES = int(os.getenv('MAX_RETRIES'))
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS'))
LLM_TIMEOUT_SECONDS = int(os.getenv('LLM_TIMEOUT_SECONDS'))




# ============ Build Statefull state ============
class Invoice_Issue_Receive(BaseModel): 
    model_config = ConfigDict(extra="forbid")

    name:str = Field(..., min_length=1, description="Person or company name")
    address: Optional[str] =Field(None, description="Full address on one line")
    phone: Optional[str] = None
    email: Optional[str] = None


class PaymentInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bank_name: Optional[str] = None
    account_name: Optional[str] = None
    account_number: Optional[str] = Field(None, description="Exactly as printed, keep spaces/dashes")



class Each_Line_Items(BaseModel): 
    model_config = ConfigDict(extra="forbid")

    description: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0, description="Quantity, or hours for service invoices")
    unit_price: float = Field(..., ge=0, description="Price per unit, or hourly rate")
    amount: float = Field(..., ge=0, description="Each line total = quantity x unit_price")

    @model_validator(mode='after')
    def check_amount(self): # check the ammount calculate by LLM is right/wrong
        exptd_amount = round(self.quantity * self.unit_price, 2)
        if abs(exptd_amount - self.amount) > 0.01:
            raise ValueError(
                f"line '{self.description}': quantity ({self.quantity}) x unit_price "
                f"({self.unit_price}) = {exptd_amount}, but amount is {self.amount}. "
                f"Re-check which number is the quantity and which is the price."
            )
        return self




class Invice_Infos(BaseModel): 
    model_config = ConfigDict(extra='forbid') # if any extra info comes , I will pass this anomaly in loop to fix 

    inv_num: str = Field(..., min_length=1 , description="Must keep leading zeros, e.g. '01234'")
    inv_date : date = Field(..., description="ISO format YYYY-MM-DD")
    due_date: Optional[date] = Field(None, description="ISO format YYYY-MM-DD")

    currency: str = Field("USD", pattern=r"^[A-Z]{3}$", description="ISO 4217 code, '$' -> 'USD'")

    seller: Optional[Invoice_Issue_Receive] = Field(None, description="Company/person issuing the invoice")
    bill_to: Invoice_Issue_Receive = Field(..., description="Customer the invoice is addressed to")

    # ============= inv line data and related infos =============
    line_items: list[Each_Line_Items] = Field(..., min_length=1)

    subtotal: float = Field(..., ge=0)
    tax_rate_percent: Optional[float] = Field(None, ge=0, le=100, description="e.g. 10 for 10%")
    tax_amount: float = Field(0, ge=0)
    total: float = Field(..., ge=0)

    payment_info: Optional[PaymentInfo] = None # includes bank related infoss
    notes: Optional[str] = Field(None, description="Terms, payment notes")


    # ==================================================================================
    @field_validator("inv_num")
    @classmethod
    def clean_number(cls, v: str) -> str:
        v = v.strip().lstrip("#").strip()
        if not v:
            raise ValueError("Produced invoice_number is empty")
        return v


    @model_validator(mode="after")
    def check_totals(self):
        each_line_item_sum = round(sum(i.amount for i in self.line_items), 2)

        if abs(each_line_item_sum - self.subtotal) > 0.01:
            raise ValueError(
                f"line item amounts add up to {each_line_item_sum}, but subtotal is {self.subtotal}. A line item is probably missing or has a wrong amount."
            )

        if abs(self.subtotal + self.tax_amount - self.total) > 0.01:
            raise ValueError(
                f"subtotal ({self.subtotal}) + tax_amount ({self.tax_amount}) = {round(self.subtotal + self.tax_amount, 2)}, but total is {self.total}."
            )

        return self



# this the langGraph state 
class Agent_State(BaseModel): 
    current_pdf_content: str = Field("", description='Contains one Pdf data')
    current_invoice_name: str = ""
    invoices_names: list[str] = Field(default_factory=list, description='Remaining invoices that need to process')
    valid_invoice_info: dict[str, Invice_Infos] = Field(default_factory=dict)   # {pdf_name: invoice}

    failed_loop: int = Field(0, description='If Parsing fails then this will increse untill MAX_RETRIES')
    error_data: str = ""
    error_content: str=""




# ================ Build Some Helper Function ================
def clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1:
        text = text[start:end + 1]
    return text.strip()


def format_errors(e: ValidationError) -> str:
    lines = []
    for err in e.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        lines.append(f"- {loc}: {err['msg']}")

    return "\n".join(lines)



def validate_output(content):
    if not content:
        return None, "- (root): Empty response. Return the JSON object."
    try:
        invoice = Invice_Infos.model_validate_json(clean_json(content))  # ** thats validate the schema **
        return invoice, None
    except ValidationError as e:
        return None, format_errors(e)





# ================================ Build Nodes ================================
def count_invoices_Node(state: Agent_State): 
    inv = os.listdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'some_demo_invoices'))
    return {"invoices_names": inv}


def read_invoices_Node(state: Agent_State): 
    if len(state.current_pdf_content) == 0 and len(state.invoices_names)>=1: 
        # read pdf
        pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "some_demo_invoices", state.invoices_names[0])
        with pymupdf.open(pdf_path) as inv_data:
            invoice_text = "\n".join(page.get_text("text", sort=True) for page in inv_data)

        return {
            "current_invoice_name": state.invoices_names[0],
            "invoices_names": state.invoices_names[1:] , 
            "current_pdf_content": invoice_text,
        } # read the invoices_names[0] file and remove it 
    else: # means all invices data are fetched 
        return {}




def LLM_Call(messages):  # messages -> sys prompt + user Prompt
    with OpenRouter(api_key=OPENROUTER_API_KEY) as client:
        response = client.chat.send(
            model = "nvidia/nemotron-3.5-lightning:free",  # minimax/minimax-m3.1-flash:free     nvidia/nemotron-3.5-lightning:free
            messages = messages,
            temperature=0,  # 0 to 2.0
            max_tokens = LLM_MAX_TOKENS,   # minimax ct size: 1M      nemotron ct size: 1M
            reasoning={"enabled": False, "effort": "minimal", "exclude": True},
            reasoning_effort="minimal",  # xhigh, high, medium, low, minimal, none
            timeout_ms=LLM_TIMEOUT_SECONDS * 1000,  # a stuck free model can't hang the chat forever
        )
    content = response.choices[0].message.content if response.choices else None
    return content



def LLM_Call_Node(state: Agent_State): 
    print(f"Calling LLM for invoice : {state.current_invoice_name}")
    system_prompt = SYSTEM_PROMPT.format(
        schema=json.dumps(Invice_Infos.model_json_schema(), indent=2),   # pass the model schema to LLM to inform
        example=json.dumps(EXAMPLE_OUTPUT, indent=2),
    )
    user_prompt = USER_PROMPT.format(file_name=state.current_invoice_name, invoice_text=state.current_pdf_content)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content":user_prompt},
    ]
    
    
    if state.failed_loop>0: # means: prev loop was went in error .. now inlclude prev loop error in this current loop
        # 2nd time loop with pdf -- here need to iterate to resolve error
        messages += [
            {"role": "assistant", "content": state.error_content},
            {"role": "user", "content": RETRY_PROMPT.format(
                previous_output=state.error_content,
                errors=state.error_data,
            )},
        ]


    content = LLM_Call(messages)
    validated_inv , error_info = validate_output(content)
    if error_info is None: # means content is in right format
        updated = dict(state.valid_invoice_info)                  # কপি বানাও
        updated[state.current_invoice_name] = validated_inv

        return {
            "current_pdf_content": "", 
            "current_invoice_name": "", 
            "failed_loop": 0,
            "error_data" : "",
            "error_content" : "",
            "valid_invoice_info":  updated
            }
    else: 
        return {
            "failed_loop": state.failed_loop+1,
            "error_data" : f"Error dataat step: {state.failed_loop} is -- {error_info}",
            "error_content" : content,
        }


# skip node if the number of lopp is grater that max retries
def skip_invoice_Node(state: Agent_State):
    print(f"{state.current_invoice_name} failed after {MAX_RETRIES} tries\n{state.error_data}")
    return {
        "current_pdf_content": "",
        "current_invoice_name": "",
        "failed_loop": 0,
        "error_data": "",
        "error_content": "",
    }
    


# save pdf node
def save_json_Node(state: Agent_State):
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    all_invoices = {}
    for pdf_name, invoice in state.valid_invoice_info.items():
        stem = os.path.splitext(pdf_name)[0].strip()
        # "Blue White Modern Business Invoice"

        out_path = os.path.join(output_dir, stem + ".json")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(invoice.model_dump_json(indent=2))

        all_invoices[pdf_name] = invoice.model_dump(mode="json")


    # save the invcs
    with open(os.path.join(output_dir, "all_invoices.json"), "w", encoding="utf-8") as f:
        json.dump(all_invoices, f, indent=2, ensure_ascii=False)

    print("Json FIle saved done !!!")
    return {}






# ============= Build Conditional functions =============
def condition_1_check_all_invoices_consumed_or_not(state:Agent_State): 
    if len(state.current_pdf_content)==0:  # all invoices has processed -> no PDF content , so end the process
        return 'move_to_end'
    else: 
        return 'pass_to_llm'




def condition_2_error_loop(state: Agent_State):
    if len(state.current_pdf_content) == 0: 
        # means , current pdf produced a valid structure and current_pdf_content get emptyed 
        return 'next_invoice'
    elif state.failed_loop >= MAX_RETRIES: 
        # tried a lot of time .. so skip it
        return 'skip_invoice'
    else: 
        # tr-try on error
        return 'retry_llm'





# Build Graph
graph = StateGraph(Agent_State)
graph.add_node('count_invoices_Node', count_invoices_Node)
graph.add_node('read_invoices_Node', read_invoices_Node)
graph.add_node('LLM_Call_Node', LLM_Call_Node)
graph.add_node('save_json_Node', save_json_Node)
graph.add_node('skip_invoice_Node', skip_invoice_Node)




graph.add_edge(START, 'count_invoices_Node')
graph.add_edge('count_invoices_Node', 'read_invoices_Node')

graph.add_conditional_edges(
    'read_invoices_Node',
    condition_1_check_all_invoices_consumed_or_not,  
    {
        'move_to_end': 'save_json_Node', 
        'pass_to_llm': 'LLM_Call_Node'
    }
)

graph.add_conditional_edges(
    "LLM_Call_Node",
    condition_2_error_loop,
    {
        'next_invoice': 'read_invoices_Node',
        'skip_invoice': 'skip_invoice_Node',
        'retry_llm': 'LLM_Call_Node',
    }
)
graph.add_edge('skip_invoice_Node', 'read_invoices_Node')
graph.add_edge('save_json_Node', END)



# ============================= Now compile ====================================
graphObj = graph.compile()
result = graphObj.invoke(Agent_State(), config={"recursion_limit": 100})
