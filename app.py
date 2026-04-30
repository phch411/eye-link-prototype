import streamlit as st
from supabase import create_client
import pandas as pd
import re
import requests

# [필수] 페이지 설정 (최상단 1회)
st.set_page_config(page_title="Eye-Link 시스템", layout="centered")

# 1. 데이터베이스 관리 클래스
class EyeLinkDB:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
        except:
            st.error("Supabase 설정 정보를 확인해주세요.")

    def authenticate_user(self, user_id, password):
        query = self.client.table("users").select("*").eq("school_id", user_id).eq("password", password).execute()
        return query.data

    def register_user(self, user_id, password, school_name, address):
        try:
            # 중복 확인
            check = self.client.table("users").select("school_id").eq("school_id", user_id).execute()
            if len(check.data) > 0:
                return False, "이미 존재하는 아이디입니다."
            
            data = {"school_id": user_id, "password": password, "school_name": school_name, "address": address}
            self.client.table("users").insert(data).execute()
            return True, "회원가입 성공!"
        except Exception as e:
            return False, f"오류: {e}"

    def fetch_students(self):
        query = self.client.table("students").select("*").execute()
        return pd.DataFrame(query.data)

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

    def validate_password(self, pw):
        """비밀번호 실시간 검증 로직"""
        if not pw: return None, "" # 입력 전엔 메시지 없음
        
        errors = []
        if len(pw) < 8: errors.append("8자 이상")
        if not re.search("[a-zA-Z]", pw): errors.append("영문 포함")
        if not re.search("[0-9]", pw): errors.append("숫자 포함")
        if not re.search("[!@#$%^&*(),.?\":{}|<>]", pw): errors.append("특수문자 포함")
        
        if not errors:
            return True, "✅ 사용 가능한 비밀번호입니다."
        else:
            return False, f"❌ 미충족 조건: {', '.join(errors)}"

    def show_login_page(self):
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            st.title("🛡️ Eye-Link")
            st.subheader("로그인")
            with st.container(border=True):
                u_id = st.text_input("아이디")
                u_pw = st.text_input("비밀번호", type="password")
                if st.button("접속하기", use_container_width=True):
                    user = self.db.authenticate_user(u_id, u_pw)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['school_name'] = user[0]['school_name']
                        st.rerun()
                    else: st.error("정보가 일치하지 않습니다.")
                st.write("---")
                if st.button("신규 학교 등록"):
                    st.session_state['show_signup'] = True
                    st.rerun()

    def show_signup_page(self):
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            st.title("📝 학교 신규 가입")
            with st.container(border=True):
                # 1. 학교 정보 입력
                s_name = st.text_input("학교명")
                addr = st.text_input("학교 주소")
                u_id = st.text_input("사용할 아이디")
                
                # 2. 비밀번호 실시간 검증 섹션
                pw = st.text_input("비밀번호 설정", type="password")
                is_valid, msg = self.validate_password(pw)
                
                if pw: # 비밀번호 입력이 시작되면 메시지 표시
                    if is_valid: st.success(msg)
                    else: st.error(msg)
                
                pw_conf = st.text_input("비밀번호 확인", type="password")
                if pw and pw_conf and pw != pw_conf:
                    st.warning("⚠️ 비밀번호가 일치하지 않습니다.")

                st.write("---")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("가입 신청", use_container_width=True):
                        if not (s_name and addr and u_id and pw):
                            st.warning("모든 정보를 입력해 주세요.")
                        elif not is_valid:
                            st.error("비밀번호 기준을 충족해 주세요.")
                        elif pw != pw_conf:
                            st.error("비밀번호 확인이 일치하지 않습니다.")
                        else:
                            success, res = self.db.register_user(u_id, pw, s_name, addr)
                            if success:
                                st.success(res)
                                st.session_state['show_signup'] = False
                                st.rerun()
                            else: st.error(res)
                with c2:
                    if st.button("취소", use_container_width=True):
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
        else: st.info("학생 데이터가 없습니다.")

    def run(self):
        if st.session_state['logged_in']: self.show_main_dashboard()
        elif st.session_state['show_signup']: self.show_signup_page()
        else: self.show_login_page()

if __name__ == "__main__":
    app = EyeLinkApp()
    app.run()