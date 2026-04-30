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

    def get_school_info_api(self, school_name):
        """나이스 API를 통해 학교 정보 검색"""
        api_key = st.secrets["neis"]["api_key"]
        url = "https://open.neis.go.kr/hub/schoolInfo"
        params = {
            "KEY": api_key,
            "Type": "json",
            "pIndex": 1,
            "pSize": 5,
            "SCHUL_NM": school_name
        }
        try:
            response = requests.get(url, params=params)
            data = response.json()
            if "schoolInfo" in data:
                # 검색된 학교 리스트 반환
                return data["schoolInfo"][1]["row"]
            else:
                return []
        except:
            return []

    def show_signup_page(self):
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            st.title("📝 학교 신규 가입")
            with st.container(border=True):
                # 1. 학교명 검색
                search_query = st.text_input("1. 학교명 입력 (2글자 이상)", placeholder="예: 부곡초")
                
                selected_school = None
                if len(search_query) >= 2:
                    schools = self.get_school_info_api(search_query)
                    
                    if schools:
                        # 검색 결과 가공 (학교명 [주소])
                        school_options = {f"{s['SCHUL_NM']} ({s['ORG_RDNMA']})": s for s in schools}
                        selected_label = st.selectbox("2. 검색 결과에서 학교 선택", options=list(school_options.keys()))
                        selected_school = school_options[selected_label]
                    else:
                        st.warning("검색 결과가 없습니다. 정확한 학교명을 입력해 주세요.")

                # 2. API 데이터 자동 매칭
                if selected_school:
                    school_name = selected_school['SCHUL_NM']
                    address = selected_school['ORG_RDNMA']
                    neis_code = selected_school['SD_SCHUL_CODE'] # 표준 학교 코드
                    
                    st.success(f"선택됨: {school_name}")
                    st.text_input("학교 주소", value=address, disabled=True)
                    st.text_input("나이스 코드 (자동 입력)", value=neis_code, disabled=True)
                    
                    st.write("---")
                    st.markdown("### **3단계: 비밀번호 설정**")
                    pw = st.text_input("비밀번호 설정", type="password", help="8자 이상, 영문+숫자+특수문자 필수")
                    pw_conf = st.text_input("비밀번호 확인", type="password")

                    if st.button("가입 완료", use_container_width=True):
                        if pw != pw_conf:
                            st.error("비밀번호가 일치하지 않습니다.")
                        else:
                            is_valid, msg = self.check_password_strength(pw)
                            if is_valid:
                                # 아이디는 나이스 코드로 자동 저장
                                success, db_msg = self.db.register_user(neis_code, pw, school_name, address)
                                if success:
                                    st.success(db_msg)
                                    st.session_state['show_signup'] = False
                                    st.balloons()
                                    st.rerun()
                                else: st.error(db_msg)
                            else: st.error(msg)
                
                if st.button("이전으로", use_container_width=True):
                    st.session_state['show_signup'] = False
                    st.rerun()

if __name__ == "__main__":
    app = EyeLinkApp()
    app.run()