import streamlit as st
from supabase import create_client
import pandas as pd
import re
import requests

# [필수] 1순위: 페이지 설정 (절대 다른 명령보다 먼저 나와야 함)
st.set_page_config(page_title="Eye-Link 시스템", layout="centered")

# --- 데이터베이스 관리 클래스 ---
class EyeLinkDB:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
            self.neis_key = st.secrets["neis"]["api_key"]
        except Exception as e:
            st.error("설정 오류: Secrets 값을 확인하세요.")

    def get_school_list(self, keyword):
        url = "https://open.neis.go.kr/hub/schoolInfo"
        params = {"KEY": self.neis_key, "Type": "json", "pIndex": 1, "pSize": 10, "SCHUL_NM": keyword}
        try:
            res = requests.get(url, params=params).json()
            return res["schoolInfo"][1]["row"] if "schoolInfo" in res else []
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
            return True, "성공"
        except Exception as e: return False, str(e)

    def fetch_students(self):
        try:
            q = self.client.table("students").select("*").execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

# --- 앱 UI 관리 클래스 ---
class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'show_signup' not in st.session_state: st.session_state['show_signup'] = False

    def validate_pw(self, pw):
        if not pw: return None, ""
        reg = r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$"
        if re.match(reg, pw): return True, "✅ 사용 가능한 비밀번호입니다."
        return False, "❌ 8자 이상, 영문+숫자+특수문자 필수"

    def show_login(self):
        st.title("🛡️ Eye-Link")
        st.subheader("로그인")
        with st.container(border=True):
            u_id = st.text_input("아이디")
            u_pw = st.text_input("비밀번호", type="password")
            if st.button("접속", use_container_width=True):
                user = self.db.authenticate(u_id, u_pw)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['school_name'] = user[0]['school_name']
                    st.rerun()
                else: st.error("정보 불일치")
            st.write("---")
            if st.button("신규 가입"):
                st.session_state['show_signup'] = True
                st.rerun()

    def show_signup(self):
        st.title("📝 학교 가입")
        with st.container(border=True):
            s_input = st.text_input("1. 학교명 (2글자 이상)")
            school = None
            if len(s_input) >= 2:
                list = self.db.get_school_list(s_input)
                if list:
                    opts = {f"{s['SCHUL_NM']} ({s['ORG_RDNMA']})": s for s in list}
                    choice = st.selectbox("2. 학교 선택", ["선택하세요"] + list(opts.keys()))
                    if choice != "선택하세요": school = opts[choice]
            
            if school:
                st.divider()
                s_name, s_addr = school['SCHUL_NM'], school['ORG_RDNMA']
                st.success(f"📍 {s_name}")
                u_id = st.text_input("3. 아이디")
                pw = st.text_input("4. 비밀번호", type="password")
                is_v, msg = self.validate_pw(pw)
                if pw: st.success(msg) if is_v else st.error(msg)
                pw_c = st.text_input("5. 비밀번호 확인", type="password")
                if st.button("가입 완료", use_container_width=True):
                    if u_id and is_v and pw == pw_c:
                        ok, res = self.db.register(u_id, pw, s_name, s_addr)
                        if ok: 
                            st.session_state['show_signup'] = False
                            st.rerun()
                        else: st.error(res)
            if st.button("취소"):
                st.session_state['show_signup'] = False
                st.rerun()

    def show_main(self):
        st.sidebar.title(f"🏫 {st.session_state.get('school_name', '')}")
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()
        st.title("👁️ 실시간 모니터링")
        df = self.db.fetch_students()
        if not df.empty:
            st.map(df)
            st.dataframe(df)

# --- 실행부 ---
if __name__ == "__main__":
    # 클래스 생성 후 실행만 호출 (st.write 등에 절대 넣지 마세요)
    app = EyeLinkApp()
    if st.session_state['logged_in']:
        app.show_main()
    elif st.session_state['show_signup']:
        app.show_signup()
    else:
        app.show_login()