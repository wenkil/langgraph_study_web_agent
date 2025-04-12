from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, BrowserConfig
import os
import asyncio
from datetime import datetime

urls = [
    "https://www.huangli.com/huangli/2025/04_12.html",
    "https://www.zhihu.com/question/609483833/answer/3420895685"
]

# 爬虫工具
async def quick_crawl_tool(urls: list[str]):
    print('urls------>',urls)
    

    # 浏览器配置
    browser_config = BrowserConfig(
        headless=True,  # 启用无头模式
        user_agent_mode="random", # 随机生成user_agent
        text_mode=True, # 只返回文本内容
    )

    # 爬虫配置
    run_conf = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED, # 缓存模式
        stream=True,  # 是否启用流式模式
        excluded_tags=["form", "header", "footer", "nav"],
        exclude_external_links=True, # 是否排除外部链接
        exclude_social_media_links=True, # 是否排除社交媒体链接
        remove_forms=True, # 移除表单
        exclude_external_images=True, # 是否排除外部图片
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        # 或者一次性获取所有结果(默认行为)
        results = await crawler.arun_many(urls, config=run_conf)
        
        # 获取当前工作目录
        current_dir = os.getcwd()
        print('current_dir------>',current_dir)
        
        # 生成文件名 (使用时间戳确保唯一性)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(current_dir, f"crawl_results_{timestamp}.md")
        
        search_results = ''
        # 创建或打开文件用于写入
        with open(output_file, 'w', encoding='utf-8') as f:
           async for res in results:
                if res.success:
                    print(f"[OK] {res.url}, length: {len(res.markdown.raw_markdown)}")
                    # 写入URL和内容到文件
                    f.write(f"# URL: {res.url}\n\n")
                    f.write(f"{res.markdown.raw_markdown}\n\n")
                    f.write("---\n\n")  # 分隔符
                    search_results += f"{res.markdown.raw_markdown}\n\n"
                else:
                    print(f"[ERROR] {res.url} => {res.error_message}")
                    # 写入错误信息到文件
                    f.write(f"# ERROR URL: {res.url}\n")
                    f.write(f"Error: {res.error_message}\n\n")
                    f.write("---\n\n")
        
        print(f"所有结果已保存到文件: {output_file}")
        return search_results

# 单独调试时打开注释
# if __name__ == "__main__":
#    asyncio.run(quick_crawl_tool(urls))