import streamlit as st

st.set_page_config(page_title="Heal Loudly", page_icon="💙")

st.title("Heal Loudly Movement")
st.write("Welcome! This space is built for healing, sharing, and community.")

# Simple interaction test
user_input = st.text_input("What is on your mind today?")
if st.button("Share"):
    if user_input:
        st.success(f"Thank you for sharing: '{user_input}'. Your voice matters!")
    else:
        st.warning("Please enter a message first.")

