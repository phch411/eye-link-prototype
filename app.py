import streamlit as st
from supabase import create_client
import pandas as pd
import re

# [수정 1] 페이지 설정을 코드의 가장 첫 부분으로 이동 (이게 핵심입니다!)
st.set_page_config(page_title="Eye-Link 시스템", layout="centered")

# 1. 데이터베이스 관리 클래스 (이전과 동일)
class EyeLinkDB:
    def __init__(self):
        # secrets가 설정되어 있는지 확인 필요
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
        except Exception as e:
            st.error("Supabase 연결 정보를 확인할 수 없습니다. Secrets 설정을 확인해 주세요.")

    def authenticate_user(self, school_id, password):
        try:
            query = self.client.table("users").select("*").eq("school_id", school_id).eq("password", password).execute()
            return query.data
        except: return []

    def register_user(self, neis_code, password, school_name, address):
        try:
            data = {"school_id": neis_code, "password": password, "school_name": school_name, "address": address}
            self.client.table("users").insert(data).execute()
            return True, "등록 완료!"
        except Exception as e: return False, str(e)

    def fetch_students(self):
        try:
            query = self.client.table("students").select("*").execute()
            return pd.DataFrame(query.data)
        except: return pd.DataFrame()

# 2. UI 및 비즈니스 로직 제어 클래스
class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        self._initialize_session()

    def _initialize_session(self):
        if 'logged_in' not in st.session_state:
            st.session_state['logged_in'] = False
        if 'show_signup' not in st.session_state:
            st.session_state['show_signup'] = False

    def check_password_strength(self, pw):
        if len(pw) < 8 or not re.search("[a-zA-Z]", pw) or not re.search("[0-9]", pw) or not re.search("[!@#$%^&*()]", pw):
            return False, "8자 이상, 영문+숫자+특수문자 조합이 필요합니다."
        return True, ""

    # [수정 2] 각 화면 함수에서 st.set_page_config를 모두 삭제했습니다.
    def show_login_page(self):
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            st.title("🛡️ Eye-Link")
            st.subheader("로그인")
            with st.container(border=True):
                s_id = st.text_input("나이스 코드 (ID)")
                s_pw = st.text_input("비밀번호", type="password")
                if st.button("접속하기", use_container_width=True):
                    user = self.db.authenticate_user(s_id, s_pw)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['school_name'] = user[0]['school_name']
                        st.rerun()
                    else: st.error("정보가 틀립니다.")
                st.write("---")
                if st.button("신규 등록"):
                    st.session_state['show_signup'] = True
                    st.rerun()

    def show_signup_page(self):
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            st.title("📝 학교 가입")
            with st.container(border=True):
                addr = st.text_input("학교 주소")
                neis = st.text_input("나이스 코드")
                name = st.text_input("학교명")
                pw = st.text_input("비밀번호", type="password")
                if st.button("가입 신청", use_container_width=True):
                    is_valid, msg = self.check_password_strength(pw)
                    if is_valid:
                        success, db_msg = self.db.register_user(neis, pw, name, addr)
                        if success: 
                            st.session_state['show_signup'] = False
                            st.rerun()
                        else: st.error(db_msg)
                    else: st.error(msg)
                if st.button("이전으로"):
                    st.session_state['show_signup'] = False
                    st.rerun()

    def show_main_dashboard(self):
        st.sidebar.title(f"🏫 {st.session_state['school_name']}")
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()
            
        st.title("👁️ 실시간 모니터링")
        df = self.db.fetch_students()
        if not df.empty:
            st.map(df)
            st.dataframe(df)
        else: st.info("데이터 로딩 중...")

    def run(self):
        if st.session_state['logged_in']:
            self.show_main_dashboard()
        elif st.session_state['show_signup']:
            self.show_signup_page()
        else:
            self.show_login_page()

if __name__ == "__main__":
    app = EyeLinkApp()
    app.run()