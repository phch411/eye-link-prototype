import streamlit as st
from supabase import create_client
import pandas as pd
import re
import requests

# [필수] 1순위: 페이지 설정 (코드 최상단 1회 실행)
st.set_page_config(page_title="Eye-Link 시스템", layout="centered")

# --- 1. 데이터베이스 및 API 관리 클래스 ---
class EyeLinkDB:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
            self.neis_key = st.secrets["neis"]["api_key"]
        except Exception as e:
            st.error("설정 오류: Streamlit Secrets를 확인해주세요.")

    def get_school_list(self, keyword):
        url = "https://open.neis.go.kr/hub/schoolInfo"
        params = {"KEY": self.neis_key, "Type": "json", "pIndex": 1, "pSize": 10, "SCHUL_NM": keyword}
        try:
            res = requests.get(url, params=params).json()
            if "schoolInfo" in res:
                return res["schoolInfo"][1]["row"]
            return []
        except: return []

    def authenticate(self, u_id, pw):
        try:
            q = self.client.table("users").select("*").eq("school_id", u_id).eq("password", pw).execute()
            return q.data
        except: return []

    def register(self, u_id, pw, name, addr):
        try:
            check = self.client.table("users").select("school_id").eq("school_id", u_id).execute()
            if len(check.data) > 0: return False, "이미 존재하는 아이디입니다."
            data = {"school_id": u_id, "password": pw, "school_name": name, "address": addr}
            self.client.table("users").insert(data).execute()
            return True, "회원가입이 완료되었습니다!"
        except Exception as e: return False, f"DB 오류: {str(e)}"

    def fetch_students(self):
        try:
            q = self.client.table("students").select("*").execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

# --- 2. UI 및 비즈니스 로직 제어 클래스 ---
class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'show_signup' not in st.session_state: st.session_state['show_signup'] = False
        if 'user_info' not in st.session_state: st.session_state['user_info'] = None

    def validate_pw(self, pw):
        if not pw: return None, ""
        reg = r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$"
        if re.match(reg, pw): return True, "✅ 안전한 비밀번호입니다."
        return False, "❌ 8자 이상, 영문+숫자+특수문자 필수"

    def show_login_page(self):
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
                    st.rerun()
                else: st.error("로그인 정보를 확인해주세요.")
            st.write("---")
            if st.button("신규 학교 등록"):
                st.session_state['show_signup'] = True
                st.rerun()

    def show_signup_page(self):
        st.title("📝 학교 가입")
        with st.container(border=True):
            s_input = st.text_input("1. 학교명 검색 (2글자 이상)")
            selected_school = None
            
            if len(s_input) >= 2:
                school_list = self.db.get_school_list(s_input)
                if school_list:
                    # [수정 포인트] 가독성을 높여 에러를 방지한 딕셔너리 생성 로직
                    opts = {}
                    for s in school_list:
                        label = f"{s['SCHUL_NM']} ({s['ORG_RDNMA']})"
                        opts[label] = s
                    
                    choice = st.selectbox("2. 학교 선택", options=["선택하세요"] + list(opts.keys()))
                    if choice != "선택하세요":
                        selected_school = opts[choice]
                else: st.warning("검색 결과가 없습니다.")

            if selected_school:
                st.divider()
                s_name, s_addr = selected_school['SCHUL_NM'], selected_school['ORG_RDNMA']
                st.info(f"📍 선택: {s_name}")
                u_id = st.text_input("3. 아이디 설정")
                pw = st.text_input("4. 비밀번호 설정", type="password")
                is_v, msg = self.validate_pw(pw)
                if pw: (st.success(msg) if is_v else st.error(msg))
                pw_c = st.text_input("5. 비밀번호 확인", type="password")
                
                if st.button("가입 신청", use_container_width=True):
                    if u_id and is_v and pw == pw_c:
                        ok, res = self.db.register(u_id, pw, s_name, s_addr)
                        if ok:
                            st.success(res)
                            st.balloons()
                            st.session_state['show_signup'] = False
                            st.rerun()
                        else: st.error(res)
            
            st.write("---")
            if st.button("취소 및 이전으로"):
                st.session_state['show_signup'] = False
                st.rerun()

    def show_dashboard(self):
        user = st.session_state['user_info']
        st.sidebar.title(f"🏫 {user['school_name']}")
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()
        st.title("👁️ 실시간 모니터링")
        df = self.db.fetch_students()
        if not df.empty:
            st.map(df)
            st.dataframe(df, use_container_width=True)
        else: st.info("학생 데이터가 없습니다.")

if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state['logged_in']: app.show_dashboard()
    elif st.session_state['show_signup']: app.show_signup_page()
    else: app.show_login_page()