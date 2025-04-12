import os
from typing import Literal
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, AIMessageChunk
from langgraph.graph import Graph, StateGraph, MessagesState, END
from langchain_community.chat_models import QianfanChatEndpoint
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
import asyncio
from langchain_core.runnables.graph import MermaidDrawMethod
from langchain_core.utils.function_calling import convert_to_openai_function

# 百度千帆的调用方式
# llm = QianfanChatEndpoint(
#     model="ERNIE-Speed-128K",
#     streaming=True,  # 启用流式输出
#     api_key=os.getenv('QIANFAN_AK', ''),
#     secret_key=os.getenv('QIANFAN_SK', '')
# )

# 硅基流动的api调用方式
llm = ChatOpenAI(
    #THUDM/glm-4-9b-chat
    #Qwen/Qwen2.5-7B-Instruct
    model="THUDM/glm-4-9b-chat",
    streaming=False,  # 启用流式输出
    api_key=os.getenv('SILICONFLOW_API_KEY', ''), 
    base_url=os.getenv('SILICONFLOW_BASE_URL', ''),
    temperature=0.1,
)

# 定义工具
@tool
def get_weather(query: str):
    """用于获取天气信息。"""
    return ["今天天气晴朗，温度20度", "明天天气多云，温度25度"]

tools = [get_weather]
llm_with_tools = llm.bind_tools(tools)

# 创建工具列表的函数版本
functions = [convert_to_openai_function(t) for t in tools]
# 创建tool节点
tool_node = ToolNode(tools)

# llm的调用
async def chat_bot(state: MessagesState):
    """生成流式回复的节点函数"""
    messages = state["messages"]
    # response = await llm.ainvoke(messages)
    response = await llm_with_tools.ainvoke(
        messages,
        functions=functions,
        function_call="auto"
    )
    return {"messages": [response]}

# 4.定义边的逻辑判断（条件边），判断是否继续
def tool_router(state: MessagesState) -> Literal["tools", "__end__"]: #Literal用于限制返回的值的可选值
    print('state------>',state,'\n')
    messages = state['messages']
    last_message = messages[-1]
    print('last_message------>',last_message,'\n')
    print('last_message.tool_calls------>',last_message.tool_calls,'\n')
    if last_message.tool_calls: #判断models是否返回tools调用，有则告诉调用tools节点，否则结束
        return "tools"
    return END

# 创建工作流程
workflow = StateGraph(MessagesState)
# 添加节点
workflow.add_node("chat_bot", chat_bot)
# 设置入口节点
workflow.set_entry_point("chat_bot")
# 添加tool节点
workflow.add_node("tools", tool_node)
# 从tools节点指向chat_bot节点，以便可能的后续交互
workflow.add_edge("tools", "chat_bot")
workflow.add_conditional_edges(
    "chat_bot",
    tool_router,    #判断下一个调用的节点
)
# 编译图
app_graph = workflow.compile()



# 定义一个将图导出为PNG的函数
def export_graph_to_png():
    """
    将LangGraph图导出为PNG格式
    Returns:
        str: 生成的PNG文件路径
    """
    try:
        output_file='简单的chatbot-'+datetime.now().strftime("%Y-%m-%d_%H-%M-%S")+".png"
        app_graph.get_graph().draw_mermaid_png(
            draw_method=MermaidDrawMethod.API,
            output_file_path=output_file
        )
        # return True
    except Exception as e:
        print(f"导出PNG图形时出错: {e}")
        return None

# 测试运行函数
async def run_streaming_chain():
    """运行graph的链"""
    print("开始生成回复...\n")
    messages = [
        SystemMessage(content="你是一个智能助手，使用专业且准确的语言回复用户的问题，且使用中文进行回复"),
        HumanMessage(content="帮我查一下今明两天的天气")
    ]
    
    # 初始化状态
    initial_state = {"messages": messages, "streamed_output": []}
    
    # stream_mode values的效果
    # async for event in app_graph.astream(initial_state, config={"configurable": {"thread_id": "1"}}, stream_mode="values"):
    #     # print('event------>',event,'\n\n')
    #     if "messages" in event:
    #         event["messages"][-1].pretty_print()
    #     pass
    
    # stream_mode messages的流式效果
    async for event in app_graph.astream(initial_state, stream_mode='messages'):
        # print('event------>',event,'\n\n')
        if isinstance(event, tuple):
            chunk: AIMessageChunk = event[0]
            if chunk.type == 'AIMessageChunk':
                print('event里监听到的流式输出------>',chunk.content,'\n\n')
    
    # print("\n回复完成")
    
    # 展示图形
    try:
        # 导出为PNG
        export_graph_to_png()
    except Exception as e:
        print(f"图表绘制出错: {e}")

# 运行流式输出
if __name__ == "__main__":
    asyncio.run(run_streaming_chain())
