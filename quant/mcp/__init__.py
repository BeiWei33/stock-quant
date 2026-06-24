"""Stock Quant MCP Server - 让 AI 直接驱动量化流程。

使用方法：
    python -m quant.mcp.server              # stdio 模式（默认）
    python -m quant.mcp.server --transport sse  # SSE 模式
"""

from .server import main

if __name__ == "__main__":
    main()
