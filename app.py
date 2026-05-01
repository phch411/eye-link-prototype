import streamlit as st
from supabase import create_client
import pandas as pd
import re
import requests

# [필수] 1순위: 페이지 설정 (코드 최상단에 1회만 실행)
st.set_page_config(page_title="Eye-Link 시스템", layout="centered")

# --- 1. 데이터베이스 및 API 관리 클래스 (Model) ---
class EyeLinkDB:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
            self.neis_key = st.secrets["neis"]["api_key"]
        except Exception as e:
            st.error("설정 오류: Streamlit Cloud의 Secrets 설정을 확인해주세요.")

    def get_school_list(self, keyword):
        """나이스 API 학교 검색"""
        url = "https://open.neis.go.kr/hub/schoolInfo"
        params = {"KEY": self.neis_key, "Type": "json", "pIndex": 1, "pSize": 10, "SCHUL_NM": keyword}
        try:
            res = requests.get(url, params=params).json()
            if "schoolInfo" in res:
                return res["schoolInfo"][1]["row"]
            return []
        except:
            return []

    def authenticate(self, u_id, pw):
        """로그인 인증: ID와 PW가 일치하는 유저 탐색"""
        try:
            q = self.client.table("users").select("*").eq("school_id", u_id).eq("password", pw).execute()
            return q.data
        except:
            return []

    def register(self, u_id, pw, name, addr):
        """회원가입: 데이터를 Supabase 'users' 테이블에 삽입"""
        try:
            # 아이디 중복 체크
            check = self.client.table("users").select("school_id").eq("school_id", u_id).execute()
            if len(check.data) > 0:
                return False, "이미 존재하는 아이디입니다."
            
            # 데이터 삽입 (address 컬럼이 DB에 있어야 함)
            data = {
                "school_id": u_id, 
                "password": pw, 
                "school_name": name, 
                "address": addr
            }
            self.client.table("users").insert(data).execute()
            return True, "회원가입이 완료되었습니다!"
        except Exception as e:
            return False, f"DB 오류: {str(e)}"

    def fetch_students(self):
        """학생 데이터 가져오기"""
        try:
            q = self.client.table("students").select("*").execute()
            return pd.DataFrame(q.data)
        except:
            return pd.DataFrame()

# --- 2. UI 및 비즈니스 로직 제어 클래스 (Controller/View) ---
class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        # 세션 초기화
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'show_signup' not in st.session_state: st.session_state['show_signup'] = False
        if 'user_info' not in st.session_state: st.session_state['user_info'] = None

    def validate_pw(self, pw):
        """비밀번호 실시간 검증 로직"""
        if not pw: return None, ""
        reg = r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$"
        if re.match(reg, pw):
            return True, "✅ 안전한 비밀번호입니다."
        return False, "❌ 8자 이상, 영문+숫자+특수문자 필수"

    def show_login_page(self):
        """로그인 화면"""
        st.title("🛡️ Eye-Link")
        st.subheader("학교 관리자 로그인")
        with st.container(border=True):
            u_id = st.text_input("아이디 (ID)")
            u_pw = st.text_input("비밀번호", type="password")
            if st.button("로그인", use_container_width=True):
                user = self.db.authenticate(u_id, u_pw)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = user[0]
                    st.success(f"{user[0]['school_name']}님, 환영합니다!")
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호를 확인해주세요.")
            
            st.write("---")
            if st.button("신규 학교 등록 (회원가입)"):
                st.session_state['show_signup'] = True
                st.rerun()

    def show_signup_page(self):
        """회원가입 화면 (학교 검색 연동)"""
        st.title("📝 학교 가입")
        with st.container(border=True):
            # 1. 학교명 검색
            s_input = st.text_input("1. 학교명 검색 (2글자 이상)")
            selected_school = None
            
            if len(s_input) >= 2:
                school_list = self.db.get_school_list(s_input)
                if school_list:
                    opts = {f"{s['SCHUL_NM']} ({s['