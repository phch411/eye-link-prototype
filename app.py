import streamlit as st
from supabase import create_client
import pandas as pd
import re

# 1. 데이터베이스 관리 클래스 (Model)
class EyeLinkDB:
    def __init__(self):
        self.url = st.secrets["supabase"]["url"]
        self.key = st.secrets["supabase"]["key"]
        self.client = create_client(self.url, self.key)

    def authenticate_user(self, school_id, password):
        """사용자 인증"""
        try:
            query = self.client.table("users").select("*")\
                .eq("school_id", school_id)\
                .eq("password", password).execute()
            return query.data
        except Exception as e:
            st.error(f"인증 중 오류 발생: {e}")
            return []

    def register_user(self, neis_code, password, school_name, address):
        """새로운 학교 등록 (나이스 코드를 아이디로 사용)"""
        try:
            # 중복 확인
            check = self.client.table("users").select("school_id").eq("school_id", neis_code).execute()
            if len(check.data) > 0:
                return False, "이미 등록된 나이스 코드입니다."
            
            data = {
                "school_id": neis_code,
                "password": password,
                "school_name": school_name,
                "address": address
            }
            self.client.table("users").insert(data).execute()
            return True, "학교 등록이 완료되었습니다!"
        except Exception as e:
            return False, f"DB 등록 오류: {e}"

    def fetch_students(self):
        """학생 실시간 데이터 호출"""
        try:
            query = self.client.table("students").select("*").execute()
            return pd.DataFrame(query.data)
        except Exception as e:
            return pd.DataFrame()

# 2. UI 및 비즈니스 로직 제어 클래스 (Controller/View)
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
        """비밀번호 규칙: 8자 이상, 영문+숫자+특수문자 조합"""
        if len(pw) < 8:
            return False, "비밀번호는 최소 8자 이상이어야 합니다."
        if not re.search("[a-zA-Z]", pw) or not re.search("[0-9]", pw) or not re.search("[!@#$%^&*(),.?\":{}|<>]", pw):
            return False, "영문, 숫자, 특수문자를 모두 포함해야 합니다."
        return True, ""

    def show_login_page(self):
        st.set_page_config(page_title="Eye-Link 로그인", layout="centered")
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            st.title("🛡️ Eye-Link")
            st.subheader("학교 관리 시스템 로그인")
            with st.container(border=True):
                s_id = st.text_input("나이스 코드 (ID)")
                s_pw = st.text_input("비밀번호", type="password")
                if st.button("접속하기", use_container_width=True):
                    user = self.db.authenticate_user(s_id, s_pw)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['school_name'] = user[0]['school_name']
                        st.rerun()
                    else:
                        st.error("로그인 정보가 올바르지 않습니다.")
                st.write("---")
                if st.button("우리 학교 신규 등록"):
                    st.session_state['show_signup'] = True
                    st.rerun()

    def show_signup_page(self):
        st.set_page_config(page_title="Eye-Link 회원가입", layout="centered")
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            st.title("📝 학교 신규 가입")
            with st.container(border=True):
                st.markdown("### **1단계: 학교 정보**")
                addr = st.text_input("학교 주소")
                neis = st.text_input("나이스(NEIS) 코드", help="아이디로 자동 설정됩니다.")
                name = st.text_input("학교명 (예: 부곡초등학교)")
                
                st.markdown("### **2단계: 계정 설정**")
                st.text_input("아이디 (나이스 코드 자동 적용)", value=neis, disabled=True)
                pw = st.text_input("비밀번호", type="password", help="8자 이상, 영문+숫자+특수문자 필수")
                pw_conf = st.text_input("비밀번호 확인", type="password")
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("가입 신청", use_container_width=True):
                        if not (addr and neis and name and pw):
                            st.warning("모든 필드를 입력해 주세요.")
                        elif pw != pw_conf:
                            st.error("비밀번호가 일치하지 않습니다.")
                        else:
                            is_valid, msg = self.check_password_strength(pw)
                            if not is_valid:
                                st