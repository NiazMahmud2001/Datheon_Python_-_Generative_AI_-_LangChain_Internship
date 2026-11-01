from langchain_tavily import TavilySearch
'''
tool = TavilySearch(
    max_results=5,
    topic="general",                                     # "general", "news" , "finance"
    # include_answer=False,                              # True/"basic"   or False/"advanced"
    # include_raw_content=False,                         # True/"markdown"->return html markdown  or False/"text"->return plain text
    # include_images=False,                              # True/False
    # include_image_descriptions=False,                  # True/False
    # search_depth="basic",                              # "basic"/"advanced"
    # time_range="day",                                  # "day", "week", "month" , "year"
    # start_date=None,                                   # format: YYYY-MM-DD -> None/"2026-01-01"
    # end_date=None,                                     # format: YYYY-MM-DD -> None/"2026-01-01"
    # include_domains=None,                              # ["wikipedia.org"] //// None/list -> at most 300 ta domain pass kora jai
    # exclude_domains=None,                              # which dome will be excluded //// None/liat -> at most 150 ta link
    # include_usage= False 
)
'''


import os 
print(os.path.abspath("./"))
print(os.path.dirname(os.path.abspath(__file__)))


from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


llm = ChatOpenAI(
    model="nvidia/nemotron-3.5-lightning:free",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    temperature=0,
)

messages = [
    SystemMessage(content="You are a helpful data science assistant."),
    HumanMessage(content="What is the difference between overfitting and underfitting?")
]
response = llm.invoke(messages)
print(response.content)
