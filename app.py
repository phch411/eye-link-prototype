import streamlit as st
from supabase import create_client
import pandas as pd
import re
import requests

# [필수] 페이지 설정 최상단 1회
st.set_page_config(page_title="Eye-Link 시스템", layout="centered")

# 1. 데이터베이스 및 API 관리 클래스
class EyeLinkDB:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
            self.neis_key = st.secrets["neis"]["api_key"]
        except:
            st.error("설정 정보(Secrets)를 확인해주세요.")

    def get_school_list(self, keyword):
        """나이스 API로 학교 목록 검색"""
        url = "https://open.neis.go.kr/hub/schoolInfo"
        params = {"KEY": self.neis_key, "Type": "json", "pIndex": 1, "pSize": 10, "SCHUL_NM": keyword}
        try:
            res = requests.get(url, params=params).json()
            return res["schoolInfo"][1]["row"]
        except: return []

    def authenticate_user(self, u_id, pw):
        query = self.client.table("users").select("*").eq("school_id", u_id).eq("password", pw).execute()
        return query.data

    def register_user(self, u_id, pw, s_name, addr):
        try:
            check = self.client.table("users").select("school_id").eq("school_id", u_id).execute()
            if len(check.data) > 0: return False, "이미 존재하는 아이디입니다."
            data = {"school_id": u_id, "password": pw, "school_name": s_name, "address": addr}
            self.client.table("users").insert(data).execute()
            return True, "가입 성공!"
        except Exception as e: return False, str(e)

# 2. UI 및 흐름 제어 클래스
class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        self._initialize_session()

    def _initialize_session(self):
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'show_signup' not in st.session_state: st.session_state['show_signup'] = False

    def validate_password(self, pw):
        if not pw: return None, ""
        errors = []
        if len(pw) < 8: errors.append("8자 이상")
        if not re.search("[a-zA-Z]", pw): errors.append("영문")
        if not re.search("[0-9]", pw): errors.append("숫자")
        if not re.search("[!@#$%^&*()]", pw): errors.append("특수문자")
        return (True, "✅ 안전함") if not errors else (False, f"❌ 미흡: {', '.join(errors)}")

    def show_login_page(self):
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            st.title("🛡️ Eye-Link")
            with st.container(border=True):
                u_id = st.text_input("아이디")
                u_pw = st.text_input("비밀번호", type="password")
                if st.button("접속", use_container_width=True):
                    if self.db.authenticate_user(u_id, u_pw):
                        st.session_state['logged_in'] = True
                        st.session_state['school_name'] = u_id # 임시
                        st.rerun()
                    else: st.error("정보 불일치")
                if st.button("신규 학교 등록"):
                    st.session_state['show_signup'] = True
                    st.rerun()

    def show_signup_page(self):
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            st.title("📝 학교 가입")
            with st.container(border=True):
                # --- 학교 검색 섹션 ---
                search_nm = st.text_input("1. 학교명 입력 (2글자 이상)", placeholder="예: 부곡초")
                selected_school = None
                
                if len(search_nm) >= 2:
                    schools = self.db.get_school_list(search_nm)
                    if schools:
                        school_opts = {f"{s['SCHUL_NM']} ({s['ORG_RDNMA']})": s for s in schools}
                        choice = st.selectbox("2. 학교 선택", options=["선택하세요"] + list(school_opts.keys()))
                        if choice != "선택하세요":
                            selected_school = school_opts[choice]
                    else: st.warning("검색 결과가 없습니다.")

                # --- 계정 설정 섹션 ---
                if selected_school:
                    st.divider()
                    s_name = selected_school['SCHUL_NM']
                    addr = selected_school['ORG_RDNMA']
                    
                    st.success(f"📍 선택됨: {s_name}")
                    u_id = st.text_input("3. 사용할 아이디")
                    pw = st.text_input("4. 비밀번호", type="password")
                    is_v, msg = self.validate_password(pw)
                    if pw: (st.success(msg) if is_v else st.error(msg))
                    
                    pw_c = st.text_input("5. 비밀번호 확인", type="password")
                    if pw != pw_c: st.warning("비밀번호 불일치")

                    if st.button("가입 신청", use_container_width=True):
                        if u_id and is_v and pw == pw_c:
                            success, res = self.db.register_user(u_id, pw, s_name, addr)
                            if success:
                                st.session_state['show_signup'] = False
                                st.rerun()
                            else: st.error(res)
                        else: st.warning("모든 조건을 충족해주세요.")
                
                if st.button("취소"):
                    st.session_state['show_signup'] = False
                    st.rerun()

    def run(self):
        if st.session_state['logged_in']:
            st.title("👁️ 모니터링 중")
            if st.button("로그아웃"):
                st.session_state['logged_in'] = False
                st.rerun()
        elif st.session_state['show_signup']: self.show_signup_page()
        else: self.show_login_page()

if __name__ == "__main__":
    app = EyeLinkApp()
    app.run()