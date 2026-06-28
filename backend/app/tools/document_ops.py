"""Document parsing tools using LangChain DocumentLoaders."""

import os
from langchain_core.tools import tool
from langchain_community.document_loaders import TextLoader, PyPDFLoader, CSVLoader


@tool
def read_document(file_path: str, page: int = 0, chunk_size: int = 4000) -> str:
    """读取并解析文档文件。支持 .txt、.md、.pdf、.csv 格式。

    Args:
        file_path: 文档文件路径
        page: PDF 页码（从0开始），非 PDF 文件忽略
        chunk_size: CSV 等文件的分段大小
    """
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == '.pdf':
            loader = PyPDFLoader(file_path)
            pages = loader.load()
            if page >= len(pages):
                return f"错误: PDF 只有 {len(pages)} 页，请求第 {page + 1} 页"
            return pages[page].page_content[:chunk_size]

        elif ext == '.csv':
            loader = CSVLoader(file_path)
            docs = loader.load()
            return docs[0].page_content[:chunk_size] if docs else "(CSV 文件为空)"

        elif ext in ('.txt', '.md', '.py', '.js', '.ts', '.json', '.yaml', '.yml', '.html', '.css', '.xml'):
            loader = TextLoader(file_path, autodetect_encoding=True)
            docs = loader.load()
            return docs[0].page_content[:chunk_size] if docs else "(文件为空)"

        else:
            loader = TextLoader(file_path, autodetect_encoding=True)
            docs = loader.load()
            return docs[0].page_content[:chunk_size] if docs else "(文件为空)"
    except FileNotFoundError:
        return f"错误: 文件未找到 - {file_path}"
    except Exception as e:
        return f"错误: 无法解析文档 - {str(e)}"
