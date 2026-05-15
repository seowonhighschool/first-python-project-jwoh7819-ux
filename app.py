import streamlit as st
 
st.title("실dddddssssssss습")
 
name = st.text_input("이름을 입력하세요")
if name:
    st.write(f"{name}님 안녕하세요")