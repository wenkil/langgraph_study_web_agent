### Welcome to star~~
[中文版](./README.md)

The learning process has been recorded on the blog, welcome to communicate: https://wenkil.github.io/tags/Langgraph/

## Project Introduction

This is a project documenting a personal learning process, based on the LangGraph framework to create an AI assistant capable of performing web searches and web content scraping. The assistant can analyze user questions, determine whether information needs to be retrieved from the internet, then obtain relevant links through search engines, scrape webpage content, and generate comprehensive answers.

The project provides more comprehensive and in-depth information retrieval capabilities than simple searches through a "Search → Scrape → Summarize" workflow.

## Core Features

- **Intelligent Conversation**: Basic chat functionality, understanding user questions
- **Web Search**: Integration with Tavily/DuckDuckGo and other search APIs
- **Web Content Scraping**: Using Crawl4AI to scrape and parse webpage content
- **Content Summarization**: Analysis and synthesis of scraped content to generate structured answers

## Workflow Diagram

![Workflow Example](./web_crawl_graph-2025-04-12_22-35-50.png)

## Installation Guide

### Requirements

- Python 3.12
- LLM API supporting Function Calling

### Environment Setup

Create environment with conda:

```bash
# Create an environment named langgraph_study_web_agent with Python 3.12
conda create -n langgraph_study_web_agent python=3.12 -y
# Activate the environment
conda activate langgraph_study_web_agent
```

### Dependencies Installation

```bash
pip install -r requirements.txt
```

### Configuration

Create a `.env` file and configure the following environment variables:

```
TAVILY_API_KEY=your_tavily_api_key
SILICONFLOW_API_KEY=your_api_key
SILICONFLOW_BASE_URL=your_base_url
```

## Implementation Details

### 1. State Graph Design

The project uses LangGraph's state graph design, containing the following nodes:

- `chat_bot`: Analyzes user questions and decides whether search tools are needed
- `search_tool`: Performs web searches to obtain relevant URLs
- `crawl4ai_tool`: Scrapes webpage content from URLs
- `summary_bot`: Analyzes scraped content and generates final answers

### 2. Web Scraping Tool

Web scraping tool developed based on the Crawl4AI library:

```python
async def quick_crawl_tool(urls: list[str]):
    """
    Scrape webpage content from the specified URL list and save to local files
    
    Args:
        urls: List of URLs to scrape
        
    Returns:
        str: Concatenated text of all scraping results
    """
    browser_config = BrowserConfig(
        headless=True,  # Enable headless mode
        user_agent_mode="random", # Randomly generate user_agent
        text_mode=True, # Return text content only
    )
    
    run_conf = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED,
        stream=True,
        excluded_tags=["form", "header", "footer", "nav"],
        exclude_external_links=True,
        exclude_social_media_links=True,
        remove_forms=True,
        exclude_external_images=True,
    )
    
    # Scrape webpages and return content
    # See source code for implementation details
```

### 3. Search and Scraping Process

A complete "Question Analysis → Search → Scrape → Summarize" workflow is implemented through conditional routing:

```python
# Set entry point
graph_builder.set_entry_point("chat_bot")

# Add conditional edges
graph_builder.add_conditional_edges(
    "chat_bot",
    route_search_tool,
    path_map={"search_tool": "search_tool", "END": END}
)

# Add other edges
graph_builder.add_edge("search_tool", "crawl4ai_tool")
graph_builder.add_edge("crawl4ai_tool", "summary_bot")
graph_builder.add_edge("summary_bot", END)
```

## Usage Example

```python
# Create initial message
system_message = SystemMessage(content=f"""
    # You are a powerful AI assistant, skilled at searching and analyzing information from the web.
    ## For user questions, first analyze whether you have sufficient knowledge to answer, otherwise perform a web search.
    ## If you need to query real-time or specialized information, first use the [search tool] to get links to relevant content.
    ## If the [search tool] returns links, you need to use the [crawler tool] to get the specific content.
    ## Please remember that today's date is {today}.
""")

first_message = HumanMessage(content="What is crawl4ai?")

# Initialize state
initial_state = {"messages": [system_message, first_message]}

# Execute graph
async for event in graph.astream_events(initial_state):
    # Process events...
```

## Notes

1. For online PDF files (ending with .pdf), the current version of Crawl4AI cannot scrape them directly. The system will return the PDF link for users to view on their own. (This has been raised in official issues and will likely be addressed in future updates)
2. When using DuckDuckGoSearchResults, ensure `output_format="list"` is set, and the link field is "link".
3. Data privacy: Scraped content is temporarily saved in local files.

## Future Plans

- History session management
- Multi-tool collaboration support
- Web interface integration 