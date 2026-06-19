import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Load environment variables
load_dotenv()

app = FastAPI(title="Bhashini Doc Assistant API")

# Check vector database directory
DB_DIR = "./chroma_db"
if not os.path.exists(DB_DIR) or not os.listdir(DB_DIR):
    print(f"Warning: Vector store directory '{DB_DIR}' is empty or does not exist.")
    print("Please run 'python ingest.py' first to build the database.")

# Helpers for embeddings and LLM
def get_embeddings():
    openai_key = os.getenv("OPENAI_API_KEY")
    has_openai = bool(openai_key and openai_key != "your_openai_api_key_here")
    
    # Auto-detect dimension from existing chroma collection
    db_dir = "./chroma_db"
    if os.path.exists(db_dir) and os.listdir(db_dir):
        try:
            import chromadb
            client = chromadb.PersistentClient(path=db_dir)
            collection = client.get_collection("langchain")
            peek = collection.peek(1)
            if peek and "embeddings" in peek and len(peek["embeddings"]) > 0:
                dim = len(peek["embeddings"][0])
                if dim == 384:
                    from langchain_community.embeddings import HuggingFaceEmbeddings
                    return HuggingFaceEmbeddings(
                        model_name="all-MiniLM-L6-v2",
                        model_kwargs={'device': 'cpu'}
                    )
                elif dim == 1536:
                    from langchain_openai import OpenAIEmbeddings
                    return OpenAIEmbeddings(model="text-embedding-3-small")
        except Exception as e:
            print(f"Auto-detect embeddings dimension failed: {e}")

    if not has_openai:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
    else:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model="text-embedding-3-small")


def get_llm(provider: str, model_name: str, temperature: float = 0.1):
    openai_key = os.getenv("OPENAI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    
    # Auto-detect if provider is "auto"
    if provider == "auto":
        if groq_key and groq_key != "your_groq_api_key_here":
            provider = "groq"
        elif openai_key and openai_key != "your_openai_api_key_here":
            provider = "openai"
        else:
            provider = "ollama"
            
    if provider == "groq":
        if not groq_key or groq_key == "your_groq_api_key_here":
            raise HTTPException(
                status_code=400, 
                detail="Groq API Key is missing or placeholder. Please set GROQ_API_KEY in your .env file."
            )
        from langchain_groq import ChatGroq
        model = model_name if model_name else "llama-3.3-70b-versatile"
        return ChatGroq(model=model, temperature=temperature)
    elif provider == "openai":
        if not openai_key or openai_key == "your_openai_api_key_here":
            raise HTTPException(
                status_code=400, 
                detail="OpenAI API Key is missing or placeholder. Please set OPENAI_API_KEY in your .env file."
            )
        from langchain_openai import ChatOpenAI
        # Use gpt-4o-mini as default for OpenAI
        model = model_name if model_name else "gpt-4o-mini"
        return ChatOpenAI(model=model, temperature=temperature)
    else:
        # Fallback / explicit Ollama
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            try:
                from langchain_community.chat_models import ChatOllama
            except ImportError:
                from langchain_community.chat_models.ollama import ChatOllama
                
        model = model_name if model_name else "llama3"
        return ChatOllama(model=model, temperature=temperature)


# Request / Response Schemas
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    provider: str = "auto"  # "auto", "groq", "openai", "ollama"
    model: Optional[str] = None
    k: int = 4
    temperature: float = 0.1

class SourceDoc(BaseModel):
    topic: str
    source: str
    segment_name: str
    content: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceDoc]

# API Endpoints
@app.get("/api/settings")
def get_settings():
    openai_key = os.getenv("OPENAI_API_KEY")
    openai_available = bool(openai_key and openai_key != "your_openai_api_key_here")
    groq_key = os.getenv("GROQ_API_KEY")
    groq_available = bool(groq_key and groq_key != "your_groq_api_key_here")
    
    if groq_available:
        default_provider = "groq"
    elif openai_available:
        default_provider = "openai"
    else:
        default_provider = "ollama"
        
    return {
        "openai_available": openai_available,
        "groq_available": groq_available,
        "default_provider": default_provider,
        "default_openai_model": "gpt-4o-mini",
        "default_ollama_model": "llama3",
        "default_groq_model": "llama-3.3-70b-versatile"
    }

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        embeddings = get_embeddings()
        vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
        retriever = vectorstore.as_retriever(search_kwargs={"k": req.k})
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize vector store: {str(e)}. Make sure ingestion was run."
        )

    # 1. Retrieve relevant docs
    try:
        docs = retriever.invoke(req.message)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during vector retrieval: {str(e)}"
        )

    # Format retrieved docs for model context
    formatted_context_list = []
    sources = []
    for idx, doc in enumerate(docs):
        topic = doc.metadata.get("topic", "General")
        source_pages = doc.metadata.get("source", "Unknown")
        segment_name = doc.metadata.get("segment_name", "Unknown")
        content = doc.page_content.strip()
        
        formatted_context_list.append(
            f"--- Document segment {idx+1} (Topic: {topic} | Pages: {source_pages}) ---\n{content}"
        )
        sources.append(SourceDoc(
            topic=topic,
            source=source_pages,
            segment_name=segment_name,
            content=content
        ))
    
    context_str = "\n\n".join(formatted_context_list)

    # Format history for prompt
    history_str = ""
    for msg in req.history[-5:]: # Last 5 turns
        role_name = "User" if msg.role == "user" else "Assistant"
        history_str += f"{role_name}: {msg.content}\n"

    # Define prompt template
    prompt_template = """You are a highly helpful and precise technical support assistant for Bhashini APIs.
Use the following retrieved Bhashini API documentation context to answer the user's question.
If the context does not contain the answer, say "I don't know based on the provided documentation." Do not try to make up answers.
Keep technical instructions, endpoints, headers, and code payloads exact.

Retrieved Context:
{context}

Chat History:
{chat_history}

User Question: {input}
Answer:"""

    prompt = ChatPromptTemplate.from_template(prompt_template)

    # Get LLM
    try:
        llm = get_llm(req.provider, req.model, req.temperature)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize LLM provider '{req.provider}' with model '{req.model}': {str(e)}"
        )

    # Run chain
    chain = prompt | llm | StrOutputParser()
    
    try:
        answer = await chain.ainvoke({
            "context": context_str,
            "chat_history": history_str,
            "input": req.message
        })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating answer: {str(e)}"
        )

    return ChatResponse(answer=answer, sources=sources)

# Serve Frontend static files
# Make sure static directory exists
os.makedirs("static", exist_ok=True)

# Mount the static files directory at "/" root
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_index():
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Bhashini Chat Bot API is running. Please create static/index.html to view the Web UI."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)

