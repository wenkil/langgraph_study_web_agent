from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()
import asyncio
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import QianfanChatEndpoint
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.tools.ddg_search.tool import DuckDuckGoSearchResults
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage,ToolMessage
from langgraph.graph import StateGraph, START, END,MessagesState
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.runnables.graph import MermaidDrawMethod
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool

# 创建图构建器
graph_builder = StateGraph(MessagesState)

os.environ['TAVILY_API_KEY'] = os.getenv('TAVILY_API_KEY', '')

# 创建工具
@tool
def search(query: str):
    """用于浏览网络进行搜索。"""
    # search_tool = TavilySearchResults(max_results=3)
    search_tool = DuckDuckGoSearchResults(max_results=3, output_format="list") # output_format="list"
    return search_tool.invoke(query)
tools = [search]

# llm = QianfanChatEndpoint(
#     model="ernie-lite-pro-128k",
#     api_key=os.getenv('QIANFAN_AK', ''),
#     secret_key=os.getenv('QIANFAN_SK', '')
# )

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

# 创建工具列表的函数版本
functions = [convert_to_openai_function(t) for t in tools]

tools_by_name = {tool.name: tool for tool in tools}

# 定义工具节点函数
def search_tool_node(state: dict):
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        print('工具搜索结果的完整输出------>',observation,'\n')
        # 直接转为字符串
        search_result = str(observation)
        result.append(ToolMessage(content=search_result, tool_call_id=tool_call["id"]))
    return {"messages": result}

# 定义流式节点函数
async def chatbot_stream(state: MessagesState):
    """生成流式回复的节点函数"""
    print('chatbot_stream收到的完整输入------>',state,'\n')
    messages = state["messages"]
    # streamed_output = []
    # tool_calls_detected = []  # 新增：保存检测到的工具调用
    
    # 使用非流式方式接收完整返回
    response = llm_with_tools.invoke(
        messages,
        functions=functions,
        function_call="auto"
    )
    return {"messages": [response]}
    
    # 异步生成器不能使用return返回值
    # yield result_state
def route_tools(state: MessagesState) :
    """
    在条件边中使用,如果最后一条消息包含工具调用,则路由到工具节点,否则路由到结束节点。
    """
    messages = state['messages']
    last_message = messages[-1]
    # 检查是否是AI消息且有工具调用
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        # print('last_message.tool_calls------>',last_message.tool_calls,'\n')
        return "search_tool"  # 如果有工具调用，路由到工具节点
    
    return END

def route_chatbot(state: MessagesState) :
    """
    在条件边中使用,如果最后一条消息包含工具调用,则路由到工具节点,否则路由到结束节点。
    """
    messages = state['messages']
    last_message = messages[-1]
    if isinstance(last_message, ToolMessage):
        return "chatbot"
    return END

# 添加chatbot节点
graph_builder.add_node("chatbot", chatbot_stream)
# 添加工具节点
graph_builder.add_node("search_tool", search_tool_node)
# 设置入口点
graph_builder.set_entry_point("chatbot")
graph_builder.add_conditional_edges(
    "chatbot",
    route_tools
)
# 添加从tools到chatbot的边
graph_builder.add_edge("search_tool", "chatbot")
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
        output_file='workflow_graph-' + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".png"
        graph.get_graph().draw_mermaid_png(
            draw_method=MermaidDrawMethod.API,
            output_file_path=output_file
        )
    except Exception as e:
        print(f"导出PNG图形时出错: {e}")
        return None

# 异步运行函数（健壮版本）
async def run_demo():
    """异步运行LangGraph流式输出演示"""
    print("开始流式生成回答...\n")
    
    today = datetime.now().strftime("%Y-%m-%d")
    # print('当前日期:',today,'\n')
    # 创建初始消息
    system_message = SystemMessage(content=f"""
        # 你是一个善于分析的AI助手。
        ## 对于用户的所有问题，先分析是否需要调用搜索工具，再进行回复，比如查询东西，需要调用搜索工具，如果只是问问题，则不需要调用搜索工具。
        ## 请牢记今天的日期是{today},调用工具时，直接使用{today}的日期。
        - 分析示例:比如用户询问日历,黄历,新闻等实时查询相关的需要调用工具;比如询问今天的新闻或今天的日历。直接把{today}的日期作为参数传给搜索工具去做搜索。
        - 每个搜索结果都需要按照以下格式返回：
            - 标题：
            - 摘要：
            - 链接：
    """)
    first_message = HumanMessage(content="""
        请帮我搜索下室内适合种植什么花?
    """)
    
    # 初始化状态
    initial_state = {"messages": [system_message, first_message]}
    on_chat_model_stream_list = []
    try:
        # 异步执行流式输出
        async for event in graph.astream_events(initial_state, config={"configurable": {"thread_id": "1"}}, version="v2"):
            # 定义一个变量接收所有on_chat_model_stream的值
            # print('event------>',event,'\n\n')
            event_type = event['event']
            if event_type == 'on_tool_start' and event['data']:
                print('开始调用工具查询', event['data'],'\n\n')
            elif event_type == 'on_tool_end' and event['data']:
                print('工具查询结束',event['data'],'\n\n')
            elif event_type == 'on_chat_model_stream':
                print('on_chat_model_stream事件------>',event["data"]["chunk"].content,'\n\n')
                on_chat_model_stream_list.append(event["data"]["chunk"].content)
    except Exception as e:
        print(f"graph.astream_events执行出错: {e}")
    
    print("\n生成完成！","".join(on_chat_model_stream_list),'\n\n')
    # 展示图形
    try:
        # # 使用官方文档推荐的方法绘制Mermaid图
        # print("使用官方方法绘制Mermaid图...")
        mermaid_diagram = graph.get_graph().draw_mermaid()
        print(f"```mermaid\n{mermaid_diagram}\n```")
        
        # # 导出为PNG
        # print("\n正在导出为PNG图片...")
        export_graph_to_png()
    except Exception as e:
        print(f"图表绘制出错: {e}")
    

# 执行异步函数
if __name__ == "__main__":
    asyncio.run(run_demo())