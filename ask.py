import os
import sys
import argparse
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# Load environment variables
load_dotenv()

def get_embeddings():
    """
    Get embedding model matching the configuration used during ingestion.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key or openai_key == "your_openai_api_key_here":
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
    else:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model="text-embedding-3-small")

def _get_ollama_llm(model_name):
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        try:
            from langchain_community.chat_models import ChatOllama
        except ImportError:
            from langchain_community.chat_models.ollama import ChatOllama
    return ChatOllama(model=model_name, temperature=0.1)

def get_llm(use_ollama=False, ollama_model="llama3"):
    """
    Get the LLM provider based on config or command flags.
    """
    if use_ollama:
        print(f"--> [LLM] Connecting to local Ollama (model: {ollama_model})...")
        return _get_ollama_llm(ollama_model)

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key or openai_key == "your_openai_api_key_here":
        print("\n[!] OPENAI_API_KEY not found or not configured in .env.")
        print("    If you have Ollama installed and running locally, run with '--ollama' parameter.")
        print("    Otherwise, please set your OPENAI_API_KEY in the .env file.")
        print("\nAttempting to connect to Ollama (llama3) as a fallback...")
        return _get_ollama_llm("llama3")
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", temperature=0.1)

def format_docs(docs):
    """Format list of retrieved docs into a single string context."""
    formatted = []
    for i, doc in enumerate(docs):
        topic = doc.metadata.get("topic", "General")
        sources = doc.metadata.get("source", "Unknown")
        content = doc.page_content.strip()
        formatted.append(f"--- Document segment {i+1} (Topic: {topic} | Pages: {sources}) ---\n{content}")
    return "\n\n".join(formatted)

def print_sources(docs):
    """Print the exact documentation segments used for the query."""
    print("\n" + "="*50)
    print("RETRIEVED DOCUMENTATION SOURCES:")
    print("="*50)
    for i, doc in enumerate(docs):
        topic = doc.metadata.get("topic", "General")
        pages = doc.metadata.get("source", "Unknown")
        print(f"\n[{i+1}] Source Topic: {topic} (Page Files: {pages})")
        # Print a short preview of the text
        text_preview = doc.page_content[:250].replace('\n', ' ').strip()
        print(f"    Preview: \"{text_preview}...\"")
    print("="*50 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Query the Bhashini API documentation RAG pipeline.")
    parser.add_argument("query", nargs="?", type=str, help="The query question to ask the LLM.")
    parser.add_argument("--interactive", "-i", action="store_true", help="Start an interactive chat session.")
    parser.add_argument("--sources", "-s", action="store_true", help="Print retrieved documentation segments.")
    parser.add_argument("--ollama", action="store_true", help="Use local Ollama instead of OpenAI.")
    parser.add_argument("--model", type=str, default="llama3", help="Local Ollama model name to use (defaults to 'llama3').")
    args = parser.parse_args()

    # Check vector database directory
    db_dir = "./chroma_db"
    if not os.path.exists(db_dir) or not os.listdir(db_dir):
        print(f"Error: Vector store directory '{db_dir}' is empty or does not exist.")
        print("Please run 'python ingest.py' first to build the database.")
        sys.exit(1)

    # Initialize Embeddings and Vector Store
    embeddings = get_embeddings()
    vectorstore = Chroma(persist_directory=db_dir, embedding_function=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    # Get LLM
    llm = get_llm(use_ollama=args.ollama, ollama_model=args.model)

    # Prompt Template supporting Chat History
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

    # Build chain
    def retrieve_and_format(query_input):
        docs = retriever.get_relevant_documents(query_input)
        return docs, format_docs(docs)

    chain = (
        {"context": lambda x: x["context_str"], "chat_history": lambda x: x["chat_history"], "input": lambda x: x["input"]}
        | prompt
        | llm
        | StrOutputParser()
    )

    if args.interactive:
        print("\n" + "="*60)
        print("  Bhashini Documentation Assistant (LangChain RAG)")
        print("  Type 'exit' or 'quit' to end the chat.")
        print("  Type '/sources' to toggle source visibility for responses.")
        print("="*60 + "\n")
        
        chat_history = []
        show_sources = args.sources

        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            if user_input.lower() == "/sources":
                show_sources = not show_sources
                print(f"--> Source citations are now {'ENABLED' if show_sources else 'DISABLED'}.")
                continue

            # Format history for prompt
            history_str = ""
            for q, a in chat_history[-5:]: # Keep last 5 turns
                history_str += f"User: {q}\nAssistant: {a}\n"

            # Retrieve docs
            docs, context_str = retrieve_and_format(user_input)

            # Generate response
            print("Assistant: Thinking...", end="\r")
            try:
                response = chain.invoke({
                    "context_str": context_str,
                    "chat_history": history_str,
                    "input": user_input
                })
                # Clear "Thinking..." line
                print(" "*30, end="\r")
                print(f"Assistant: {response}")

                # Update history
                chat_history.append((user_input, response))

                if show_sources:
                    print_sources(docs)

            except Exception as e:
                print(" "*30, end="\r")
                print(f"Error executing request: {e}")

    else:
        # Single query mode
        query = args.query
        if not query:
            print("Error: Please provide a query (e.g. python ask.py \"What is a ULCA pipeline?\") or run with --interactive / -i.")
            sys.exit(1)

        print(f"Querying: {query}...")
        docs, context_str = retrieve_and_format(query)
        
        try:
            response = chain.invoke({
                "context_str": context_str,
                "chat_history": "",
                "input": query
            })
            print(f"\nAnswer:\n{response}\n")
            
            if args.sources:
                print_sources(docs)

        except Exception as e:
            print(f"Error executing request: {e}")

if __name__ == "__main__":
    main()
