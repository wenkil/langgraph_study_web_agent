"""
搜索工具比较示例：Tavily vs DuckDuckGo

该示例比较了LangChain中两个常用的搜索工具：
1. Tavily - 需要API密钥的AI优化搜索引擎
2. DuckDuckGo - 注重隐私的免费搜索引擎，无需API密钥

通过相同的查询，观察两种搜索工具返回结果的差异。
"""

import os
import time
import json
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.tools.ddg_search.tool import DuckDuckGoSearchResults

# 设置Tavily API密钥（如果存在）
tavily_api_key = os.getenv('TAVILY_API_KEY', '')
if tavily_api_key:
    os.environ['TAVILY_API_KEY'] = tavily_api_key


def format_results(results, tool_name):
    """
    格式化搜索结果为易读的格式
    
    Args:
        results (list or str): 搜索结果列表或字符串
        tool_name (str): 搜索工具名称
        
    Returns:
        str: 格式化后的搜索结果字符串
    """
    formatted_output = f"{tool_name} 搜索结果:\n"
    
    # 如果结果是字符串，尝试解析JSON
    if isinstance(results, str) and tool_name == "DuckDuckGo":
        try:
            parsed_results = json.loads(results)
            results = parsed_results
        except:
            return formatted_output + results
    
    # 根据不同的工具格式化结果
    if tool_name == "Tavily":
        for i, result in enumerate(results, 1):
            formatted_output += f"{i}. 标题: {result.get('title', 'N/A')}\n"
            formatted_output += f"   链接: {result.get('url', 'N/A')}\n"
            formatted_output += f"   内容: {result.get('content', 'N/A')[:150]}...\n\n"
    else:  # DuckDuckGo
        if isinstance(results, list):
            for i, result in enumerate(results, 1):
                formatted_output += f"{i}. 标题: {result.get('title', 'N/A')}\n"
                formatted_output += f"   链接: {result.get('link', 'N/A')}\n" 
                formatted_output += f"   摘要: {result.get('snippet', 'N/A')}\n\n"
        else:
            formatted_output += "无法解析搜索结果格式\n"
            
    return formatted_output


def search_with_tool(query, tool_type, max_results):
    """
    使用指定的搜索工具进行网络搜索
    
    Args:
        query (str): 搜索查询
        tool_type (str): 搜索工具类型 ("tavily" 或 "duckduckgo")
        max_results (int, optional): 最大结果数. 默认为5.
        
    Returns:
        dict: 搜索结果和状态信息
    """
    try:
        # 根据工具类型创建搜索工具
        if tool_type.lower() == "tavily":
            if not tavily_api_key:
                return {
                    "success": False,
                    "message": "未设置Tavily API密钥，无法使用Tavily搜索",
                    "results": []
                }
            search_tool = TavilySearchResults(max_results=max_results)
            tool_name = "Tavily"
        elif tool_type.lower() == "duckduckgo":
            search_tool = DuckDuckGoSearchResults(max_results=max_results, output_format="list")
            tool_name = "DuckDuckGo"
        else:
            return {
                "success": False,
                "message": f"不支持的搜索工具类型: {tool_type}",
                "results": []
            }
        
        # 计时开始
        start_time = time.time()
        
        # 调用搜索工具
        results = search_tool.invoke({"query": query})
        
        # 计时结束
        end_time = time.time()
        search_time = end_time - start_time
        
        # 检查结果
        if not results:
            return {
                "success": False,
                "message": f"{tool_name}搜索未返回任何结果",
                "results": [],
                "tool_name": tool_name,
                "search_time": search_time
            }
            
        # 格式化结果
        formatted_results = format_results(results, tool_name)
        
        return {
            "success": True,
            "message": f"{tool_name}搜索成功完成",
            "results": results,
            "formatted_results": formatted_results,
            "tool_name": tool_name,
            "search_time": search_time
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"搜索过程中出现错误: {str(e)}",
            "results": [],
            "tool_name": tool_type
        }


def compare_search_tools(query, max_results=3):
    """
    比较不同搜索工具的结果
    
    Args:
        query (str): 搜索查询
        max_results (int, optional): 每个工具返回的最大结果数. 默认为3.
    """
    print("=" * 60)
    print(f"搜索查询: '{query}'")
    print("=" * 60)
    
    # 使用DuckDuckGo搜索
    print("\n[1] 使用DuckDuckGo搜索...")
    ddg_result = search_with_tool(query, "duckduckgo", max_results)
    
    # 使用Tavily搜索 (如果有API密钥)
    print("\n[2] 使用Tavily搜索...")
    tavily_result = search_with_tool(query, "tavily", max_results)
    
    # 打印结果比较
    print("\n" + "=" * 60)
    print("搜索结果比较")
    print("=" * 60)
    
    # DuckDuckGo结果
    if ddg_result["success"]:
        print(f"\nDuckDuckGo 搜索时间: {ddg_result.get('search_time', 'N/A'):.2f} 秒")
        print(ddg_result["formatted_results"])
    else:
        print(f"\nDuckDuckGo 搜索失败: {ddg_result['message']}")
    
    # Tavily结果
    if tavily_result["success"]:
        print(f"\nTavily 搜索时间: {tavily_result.get('search_time', 'N/A'):.2f} 秒")
        print(tavily_result["formatted_results"])
    else:
        print(f"\nTavily 搜索失败: {tavily_result['message']}")
    
    # 添加差异分析
    if ddg_result["success"] and tavily_result["success"]:
        print("\n" + "-" * 60)
        print("结果差异分析:")
        print("-" * 60)
        
        # 比较结果数量
        ddg_results = ddg_result["results"]
        tavily_results = tavily_result["results"]
        
        # 处理DuckDuckGo的结果数量
        if isinstance(ddg_results, str):
            try:
                import json
                ddg_results = json.loads(ddg_results)
            except:
                ddg_results = []
                
        ddg_count = len(ddg_results) if isinstance(ddg_results, list) else 0
        tavily_count = len(tavily_results)
        
        print(f"DuckDuckGo 返回结果数量: {ddg_count}")
        print(f"Tavily 返回结果数量: {tavily_count}")
        
        # 比较响应时间
        if "search_time" in ddg_result and "search_time" in tavily_result:
            ddg_time = ddg_result["search_time"]
            tavily_time = tavily_result["search_time"]
            faster = "DuckDuckGo" if ddg_time < tavily_time else "Tavily"
            time_diff = abs(ddg_time - tavily_time)
            print(f"响应时间差异: {faster} 更快 {time_diff:.2f} 秒")


def main():
    """主函数，运行搜索工具比较示例"""
    # 示例搜索查询
    queries = [
        "2024年人工智能的主要发展趋势",
        "LangChain和LlamaIndex的比较",
        "Python和JavaScript的区别"
    ]
    
    for query in queries:
        compare_search_tools(query)
        print("\n\n" + "=" * 70 + "\n")
        
        # 暂停一下，避免搜索频率过高
        time.sleep(2)


if __name__ == "__main__":
    print("\n" + "*" * 70)
    print("* LangChain搜索工具比较: Tavily vs DuckDuckGo *".center(70))
    print("*" * 70 + "\n")
    
    if not tavily_api_key:
        print("警告: 未设置TAVILY_API_KEY环境变量，Tavily搜索将不可用\n")
    
    main() 