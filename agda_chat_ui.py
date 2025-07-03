import os
import streamlit as st
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)
from langchain.memory import ChatMessageHistory, ConversationBufferMemory
from langchain.chains import LLMChain
from pinecone import Pinecone

# Load API keys
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# Initialize Pinecone and Gemini
pc = Pinecone(api_key=PINECONE_API_KEY)
pinecone_index = pc.Index("agda-index")
embed_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

# Prompt Template
system_prompt_template = """
You are AgDA — an Agricultural Data Assistant for Kaduna State.
Use the provided documents to give insightful, specific, and useful agricultural advice.

{doc_content}

Answer the user's question using these materials and your own knowledge base.
"""

# Streamlit UI
st.set_page_config(page_title="AgDA Chatbot", page_icon="🌾")
st.title("🌾 AgDA - Agricultural Data Assistant")
st.markdown("Ask any agriculture-related question for Kaduna State and get expert-backed responses.")

# Session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": "Hello! I'm AgDA. How can I assist with your agricultural questions today?"}
    ]

# Display chat
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input box
user_input = st.chat_input("Ask your question...")

# On user input
if user_input:
    # Show user message
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # Embed and retrieve docs
    query_embed = embed_model.embed_query(user_input)
    results = pinecone_index.query(
        vector=query_embed,
        top_k=5,
        include_metadata=True
    )
    doc_chunks = [match["metadata"]["text"] for match in results.get("matches", [])]
    doc_content = "\n\n".join(doc_chunks) if doc_chunks else "No relevant documents found."

    # Format prompt
    system_prompt = system_prompt_template.format(doc_content=doc_content)

    # Prepare chat memory
    chat_history = ChatMessageHistory()
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            chat_history.add_user_message(msg["content"])
        else:
            chat_history.add_ai_message(msg["content"])

    memory = ConversationBufferMemory(
        memory_key="chat_history",
        chat_memory=chat_history,
        return_messages=True
    )

    # Chain
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanMessagePromptTemplate.from_template("{question}")
    ])

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.3,
        google_api_key=GOOGLE_API_KEY
    )

    chain = LLMChain(llm=llm, prompt=prompt, memory=memory, verbose=False)
    response = chain.invoke({"question": user_input})["text"]

    # Display bot response
    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.chat_history.append({"role": "assistant", "content": response})
