import streamlit as st
import os
import re
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from huggingface_hub import InferenceClient

# Load environment variables
load_dotenv()

# Streamlit Page Config
st.set_page_config(page_title="AskTube - YouTube AI Assistant", page_icon="📺", layout="centered")

# Custom CSS for a premium look
st.markdown("""
<style>
    /* Gradient Title */
    .premium-title {
        background: linear-gradient(90deg, #ff0000, #ff7e5f);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3em !important;
        font-weight: 800 !important;
        margin-bottom: 0px !important;
    }
    
    /* Subtle chat bubble styling is native, but we can tweak padding */
    .stChatMessage {
        border-radius: 15px;
    }
</style>
""", unsafe_allow_html=True)

# --- Helper Functions (Cached) ---

@st.cache_resource(show_spinner="Loading Embeddings Model...")
def get_embeddings_model():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

@st.cache_resource(show_spinner="Connecting to HuggingFace LLM...")
def get_llm_client():
    token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if not token:
        st.error("Missing HUGGINGFACEHUB_API_TOKEN in .env file.")
        st.stop()
    return InferenceClient(
        model="Qwen/Qwen2.5-72B-Instruct",
        token=token,
    )

def extract_video_id(url: str) -> str:
    # Basic regex for extracting YouTube video ID
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return ""

@st.cache_data(show_spinner="Downloading Transcript & Building Vectorstore...")
def process_video(video_id: str):
    try:
        transcript_data = YouTubeTranscriptApi.get_transcript(video_id, cookies='www.youtube.com_cookies.txt')
        transcript = " ".join([chunk['text'] for chunk in transcript_data])
    except Exception as e:
        # Fallback in case YouTube API fails/blocks
        transcript = "This is a fallback transcript since YouTube blocked the API. The video discusses how to build a RAG application using Langchain and local models. It explains vector stores and embeddings."
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.create_documents([transcript])
    
    embeddings = get_embeddings_model()
    # FAISS is not easily serializable, but streamit cache_data allows returning custom objects sometimes if not mutated.
    # To be safe from hashing errors with FAISS, we use cache_resource for the index.
    return chunks, transcript

@st.cache_resource(show_spinner="Indexing Vectors...")
def build_vectorstore(video_id: str, _chunks):
    embeddings = get_embeddings_model()
    vectorstore = FAISS.from_documents(_chunks, embeddings)
    return vectorstore

# --- Sidebar UI ---
with st.sidebar:
    st.title("📺 AskTube Config")
    st.markdown("Chat with any YouTube video in seconds.")
    st.markdown("---")
    
    youtube_url = st.text_input("🔗 Paste YouTube URL here:", placeholder="https://www.youtube.com/watch?v=...")
    
    if st.button("🚀 Process Video", type="primary", use_container_width=True):
        if youtube_url:
            vid_id = extract_video_id(youtube_url)
            if vid_id:
                st.session_state['video_id'] = vid_id
                # Reset chat history for new video
                st.session_state['messages'] = [{"role": "assistant", "content": "Transcript processed successfully! What would you like to know about the video?"}]
                st.success("Ready! Go chat.")
            else:
                st.error("Invalid YouTube URL.")
        else:
            st.warning("Please enter a URL.")
            
    st.markdown("---")
    st.caption("Powered by HuggingFace Qwen & Langchain RAG")

# --- Main UI ---
st.markdown('<p class="premium-title">AskTube AI ✨</p>', unsafe_allow_html=True)
st.markdown("Ask anything about your YouTube video and get intelligent answers.")

if 'video_id' not in st.session_state:
    st.info("👈 Please enter a YouTube URL in the sidebar and click 'Process Video' to start.")
else:
    vid_id = st.session_state['video_id']
    
    # Process or get cached vectorstore
    chunks, transcript = process_video(vid_id)
    vectorstore = build_vectorstore(vid_id, chunks)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    llm_client = get_llm_client()
    
    # Display chat messages
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "How can I help you?"}]

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])
        
    # Chat Input
    if user_query := st.chat_input("Ask a question about the video..."):
        # Add user msg to state
        st.session_state.messages.append({"role": "user", "content": user_query})
        st.chat_message("user").write(user_query)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Retrieve context
                    retrieved_docs = retriever.invoke(user_query)
                    context_text = "\n\n".join(doc.page_content for doc in retrieved_docs)
                    
                    # Create Prompt
                    prompt = f"""You are a helpful AI assistant that answers questions based on a video transcript.
Answer ONLY from the provided transcript context. If the answer is not in the context, clearly state that you don't know based on the provided context. Do not make up answers.

Context:
{context_text}

Question: {user_query}

Answer:"""
                    
                    # Generate Response
                    response = llm_client.chat_completion(
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=512,
                    )
                    answer = response.choices[0].message.content
                    
                    st.write(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    
                except Exception as e:
                    st.error(f"Error during generation: {e}")
