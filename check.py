import streamlit as st
import os
from dotenv import load_dotenv
load_dotenv()
st.write("Key loaded:", os.getenv("GEMINI_API_KEY") is not None)
