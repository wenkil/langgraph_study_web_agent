from datetime import datetime
import os
import sys
from dotenv import load_dotenv
load_dotenv()
import asyncio
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import QianfanChatEndpoint
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.tools.ddg_search.tool import DuckDuckGoSearchResults
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.runnables.graph import MermaidDrawMethod
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawl_tool import quick_crawl_tool

# 创建图构建器
graph_builder = StateGraph(MessagesState)

os.environ['TAVILY_API_KEY'] = os.getenv('TAVILY_API_KEY', '')

# 创建工具
@tool
def search_tool(query: str):
    """用于浏览网络进行搜索。"""
    search_tool = TavilySearchResults(max_results=1)
    # search_tool = DuckDuckGoSearchResults(num_results=1, output_format="list") # output_format="list"
    return search_tool.invoke(query)

@tool
async def crawl4ai_tool(query: list[str]):
    """用于爬取网页内容。接收URL列表，返回对应网页的内容。"""
    print('crawl4ai_tool收到的完整输入------>',query,'\n')
    urls = query
    result = await quick_crawl_tool(urls)
    return {"result": result}

tools = [search_tool, crawl4ai_tool]

# 创建llm，需要支持FunctionCalling的模型
llm = ChatOpenAI(
    #THUDM/glm-4-9b-chat
    #Qwen/Qwen2.5-7B-Instruct
    model="Qwen/Qwen2.5-7B-Instruct",
    streaming=False,  # 启用流式输出
    api_key=os.getenv('SILICONFLOW_API_KEY', ''), 
    base_url=os.getenv('SILICONFLOW_BASE_URL', ''),
    temperature=0.1,
)
llm_with_tools = llm.bind_tools(tools)

# 创建总结llm，需要使用支持FunctionCalling的模型
summary_llm = ChatOpenAI(
    model="THUDM/glm-4-9b-chat",
    streaming=False,
    api_key=os.getenv('SILICONFLOW_API_KEY', ''), 
    base_url=os.getenv('SILICONFLOW_BASE_URL', ''),
    temperature=0.1,
)

# 创建工具列表的函数版本
functions = [convert_to_openai_function(t) for t in tools]

tools_by_name = {tool.name: tool for tool in tools}

# 定义搜索工具节点函数
async def search_tool_node(state: dict):
    """搜索工具节点"""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        if tool_call["name"] == "search_tool":
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            print('搜索工具结果的完整输出------>',observation,'\n')
            
            if isinstance(observation, list):
                # 如果是数组，直接提取每个对象的URL
                urls = [item.get('url', '') for item in observation if isinstance(item, dict)]
                search_result = urls
            else:
                # 如果不是数组，将整个observation作为结果
                search_result = str(observation)
                
            result.append(ToolMessage(content=search_result, tool_call_id=tool_call["id"]))
    return {"messages": result}

# 爬取网页内容工具节点
async def crawl4ai_tool_node(state: MessagesState):
    """爬取网页内容工具节点"""
    last_message = state["messages"][-1]
    urls = last_message.content
    
    # 调用爬虫工具获取结果
    tool_response = await crawl4ai_tool.ainvoke({"query": urls})
    
    messages = []
    # 创建ToolMessage并添加到列表
    messages.append(ToolMessage(
        content=tool_response.get('result', tool_response), 
        tool_call_id=last_message.id
    ))
    
    return {"messages": messages}

# 定义流式节点函数
async def chatbot_node(state: MessagesState):
    """生成回复的节点函数"""
    messages = state["messages"]
    
    # 使用非流式方式接收完整返回
    response = await llm_with_tools.ainvoke(
        messages,
        functions=functions,
        function_call="auto"
    )
    return {"messages": [response]}

# 总结bot节点
async def summary_bot_node(state: MessagesState):
    """总结网页内容的节点"""
    messages = state["messages"]
    
    # 找出用户的原始问题
    human_messages = [msg for msg in messages if isinstance(msg, HumanMessage)]
    human_message = human_messages[0] if human_messages else None
    
    # 找出最后一个工具消息（包含抓取的网页内容）
    tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]
    last_tool_message = None
    for msg in reversed(tool_messages):
        if msg.content:
            last_tool_message = msg
            break
    
    # 创建系统消息
    system_message = SystemMessage(content="""
        ## 你是一个擅长信息整理并总结的AI助手，请根据用户的问题，并结合工具给出的信息把回复总结出来。
        - 如果有工具信息，正常执行总结；如果工具信息里是一些在线pdf，请把pdf的url和标题输出出来，告知用户来源自行查看。
        - 如果发现工具没有返回信息，如【工具执行异常，无返回结果】，请根据用户的问题，给出简要回答，但必须带上说明，说明你无法生成详细总结的原因。并让用户再次自行尝试。
        - 风格：排版按照markdown格式输出。热情，专业，有亲和力。
    """)
    
    # 构建消息列表
    summary_messages = [system_message]
    
    if human_message:
        summary_messages.append(human_message)
    
    if last_tool_message:
        tool_result_message = ToolMessage(
            content=f"以下是搜索和网页抓取工具返回的详细结果:\n\n{last_tool_message.content}", 
            tool_call_id=last_tool_message.id
        )
        summary_messages.append(tool_result_message)
    
    # 调用摘要模型
    if len(summary_messages) > 1:
        response = await summary_llm.ainvoke(summary_messages)
    else:
        response = ToolMessage(
            content="工具执行异常，无返回结果。", 
            tool_call_id=last_tool_message.id if last_tool_message else "error"
        )
    
    return {"messages": [response]}

def route_search_tool(state: MessagesState):
    """
    在条件边中使用,如果最后一条消息包含搜索工具调用,则路由到搜索工具节点,否则路由到结束节点。
    """
    messages = state['messages']
    last_message = messages[-1]
    
    # 检查是否是AI消息且有工具调用
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == "search_tool":
                return "search_tool"
    
    return END

# 添加节点到图
graph_builder.add_node("chat_bot", chatbot_node)
graph_builder.add_node("search_tool", search_tool_node)
graph_builder.add_node("crawl4ai_tool", crawl4ai_tool_node)
graph_builder.add_node("summary_bot", summary_bot_node)

# 设置入口点
graph_builder.set_entry_point("chat_bot")

# 添加条件边
graph_builder.add_conditional_edges(
    "chat_bot",
    route_search_tool,
    path_map={"search_tool": "search_tool", "END": END}
)

# 添加其他边
graph_builder.add_edge("search_tool", "crawl4ai_tool")
graph_builder.add_edge("crawl4ai_tool", "summary_bot")
graph_builder.add_edge("summary_bot", END)

# 编译图
graph = graph_builder.compile()

# 定义一个将图导出为PNG的函数
def export_graph_to_png():
    """
    将LangGraph图导出为PNG格式
    
    Returns:
        str: 生成的PNG文件路径
    """
    try:
        output_file='web_crawl_graph-' + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".png"
        graph.get_graph().draw_mermaid_png(
            draw_method=MermaidDrawMethod.API,
            output_file_path=output_file
        )
    except Exception as e:
        print(f"导出PNG图形时出错: {e}")
        return None

# 异步运行函数
async def run_demo():
    """异步运行LangGraph流式输出演示"""
    print("开始流式生成回答...\n")
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 创建初始消息
    system_message = SystemMessage(content=f"""
        # 你是一个强大的AI助手，擅长搜索和分析网络信息。
        ## 对于用户的问题，请先分析是否有足够知识进行回答，否则就要进行网络查询。如果需要查询实时或专业信息，请先使用[搜索工具]获取相关内容的链接。
        ## 如果[搜索工具]返回的是链接，需要再用[爬虫工具]获取具体内容。
        ## 请牢记今天的日期是{today}。
    """)
    
    first_message = HumanMessage(content="""
        crawl4ai是什么？
    """)
    
    # 初始化状态
    initial_state = {"messages": [system_message, first_message]}
    output_list = []
    
    try:
        # 异步执行流式输出
        async for event in graph.astream_events(initial_state, config={"configurable": {"thread_id": "8"}}, version="v2"):
            # 定义一个变量接收所有on_chat_model_stream的值
            # print('event------>',event,'\n\n')
            event_type = event['event']
            # print('event_type------>',event_type,'\n\n')
            if event_type == 'on_tool_start' and event['data']:
                print('开始调用工具查询', event['data'],'\n\n')
                pass
            elif event_type == 'on_tool_end' and event['data']:
                print('工具查询结束',event['data'],'\n\n')
                pass
            elif event_type == 'on_chat_model_stream':
                # print('on_chat_model_stream事件------>',event["data"]["chunk"].content,'\n\n')
                chunk_data = event["data"]["chunk"].content # 流式输出的内容
                output_list.append(chunk_data)
                print(chunk_data, end='', flush=True)
    except Exception as e:
        print(f"graph.astream_events执行出错: {e}")
    
    print('\n\n')
    print('************'*10)
    print("生成完成！\n","".join(output_list),'\n\n')
    print('************'*10)
    
    # 展示图形
    try:
        mermaid_diagram = graph.get_graph().draw_mermaid()
        print(f"```mermaid\n{mermaid_diagram}\n```")
        
        export_graph_to_png()
    except Exception as e:
        print(f"图表绘制出错: {e}")
    

# 执行异步函数
if __name__ == "__main__":
    asyncio.run(run_demo())