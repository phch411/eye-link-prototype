import streamlit as st
from supabase import create_client
import pandas as pd
import re
import requests

# [필수] 페이지 설정 - 앱의 가장 첫 번째 명령이어야 하며, 단 한 번만 실행되어야 합니다.
st.set_page_config(page_title="Eye-Link 시스템", layout="centered")

# 1. 데이터베이스 및 API 관리 클래스 (Model)
class EyeLinkDB:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
            self.neis_key = st.secrets["neis"]["api_key"]
        except Exception as e:
            st.error("설정 정보(Secrets)를 로드할 수 없습니다. 설정을 확인해 주세요.")

    def get_school_list(self, keyword):
        """나이스 API 학교 검색 로직"""
        url = "https://open.neis.go.kr/hub/schoolInfo"
        params = {"KEY": self.neis_key, "Type": "json", "pIndex": 1, "pSize": 10, "SCHUL_NM": keyword}
        try:
            res = requests.get(url, params=params).json()
            if "schoolInfo" in res:
                return res["schoolInfo"][1]["row"]
            return []
        except:
            return []

    def authenticate_user(self, u_id, pw):
        """사용자 인증"""
        try:
            query = self.client.table("users").select("*").eq("school_id", u_id).eq("password", pw).execute()
            return query.data
        except:
            return []

    def register_user(self, u_id, pw, s_name, addr):
        """신규 가입 등록"""
        try:
            # 중복 체크
            check = self.client.table("users").select("school_id").eq("school_id", u_id).execute()
            if len(check.data) > 0:
                return False, "이미 존재하는 아이디입니다."
            
            data = {"school_id": u_id, "password": pw, "school_name": s_name, "address": addr}
            self.client.table("users").insert(data).execute()
            return True, "학교 등록 성공!"
        except Exception as e:
            return False, str(e)

    def fetch_students(self):
        """학생 데이터 호출"""
        try:
            query = self.client.table("students").select("*").execute()
            return pd.DataFrame(query.data)
        except:
            return pd.DataFrame()

# 2. UI 제어 및 비즈니스 로직 클래스 (Controller/View)
class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        self._init_session()

    def _init_session(self):
        """세션 상태 초기화"""
        if 'logged_in' not in st.session_state:
            st.session_state['logged_in'] = False
        if 'show_signup' not in st.session_state:
            st.session_state['show_signup'] = False

    def validate_pw(self, pw):
        """비밀번호 복잡도 실시간 검증"""
        if not pw: return None, ""
        # 8자 이상, 영문, 숫자, 특수문자 포함 정규식
        reg = r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$"
        if re.match(reg, pw):
            return True, "✅ 사용 가능한 비밀번호입니다."
        return False, "❌ 조건 미달: 8자 이상 + 영문 + 숫자 + 특수문자 필수"

    def show_login_page(self):
        """중앙 로그인 화면"""
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.title("🛡️ Eye-Link")
            st.subheader("로그인")
            with st.container(border=True):
                u_id = st.text_input("아이디 (ID)")
                u_pw = st.text_input("비밀번호", type="password")
                if st.button("시스템 접속", use_container_width=True):
                    user = self.db.authenticate_user(u_id, u_pw)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['school_name'] = user[0]['school_name']
                        st.rerun()
                    else:
                        st.error("로그인 정보가 올바르지 않습니다.")
                st.write("---")
                if st.button("신규 학교 등록하기"):
                    st.session_state['show_signup'] = True
                    st.rerun()

    def show_signup_page(self):
        """중앙 회원가입 화면 (학교 검색 포함)"""
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.title("📝 학교 가입")
            with st.container(border=True):
                # 1단계: 학교 검색
                s_name_input = st.text_input("1. 학교명 (2글자 이상 입력)", placeholder="예: 부곡초")
                selected_school = None
                
                if len(s_name_input) >= 2:
                    schools = self.db.get_school_list(s_name_input)
                    if schools:
                        opts = {f"{s['SCHUL_NM']} ({s['ORG_RDNMA']})": s for s in schools}
                        choice = st.selectbox("2. 검색 결과에서 학교 선택", options=["선택하세요"] + list(opts.keys()))
                        if choice != "선택하세요":
                            selected_school = opts[choice]
                    else:
                        st.warning("검색 결과가 없습니다.")

                # 2단계: 상세 가입 정보
                if selected_school:
                    st.divider()
                    final_s_name = selected_school['SCHUL_NM']
                    final_addr = selected_school['ORG_RDNMA']
                    st.success(f"📍 선택됨: {final_s_name}")
                    
                    u_id = st.text_input("3. 사용할 아이디 설정")
                    pw = st.text_input("4. 비밀번호 설정", type="password")
                    
                    # 실시간 비밀번호 검증 피드백
                    is_v, msg = self.validate_pw(pw)
                    if pw:
                        st.success(msg) if is_v else st.error(msg)
                    
                    pw_c = st.text_input("5. 비밀번호 확인", type="password")
                    
                    if st.button("가입 신청 완료", use_container_width=True):
                        if u_id and is_v and pw == pw_c:
                            success, res = self.db.register_user(u_id, pw, final_s_name, final_addr)
                            if success:
                                st.success("가입 성공! 로그인해 주세요.")
                                st.session_state['show_signup'] = False
                                st.balloons()
                                st.rerun()
                            else: st.error(res)
                        else: st.warning("모든 입력 조건을 충족해 주세요.")

                if st.button("이전으로"):
                    st.session_state['show_signup'] = False
                    st.rerun()

    def show_dashboard(self):
        """메인 모니터링 화면"""
        st.sidebar.title(f"🏫 {st.session_state.get('school_name', '')}")
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()
            
        st.title("👁️ 실시간 학생 안전 모니터링")
        df = self.db.fetch_students()
        
        if not df.empty:
            st.map(df)
            st.subheader("📋 실시간 리스트")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("현재 관리 중인 학생 데이터가 없습니다.")

    def run(self):
        """앱 상태에 따른 화면 렌더링 주입"""
        if st.session_state['logged_in']:
            self.show_dashboard()
        elif st.session_state['show_signup']:
            self.show_signup_page()
        else:
            self.show_login_page()

# 3. 앱 실행부
if __name__ == "__main__":
    # app.run()만 단독으로 호출하여 불필요한 객체 출력을 방지합니다.
    app = EyeLinkApp()
    app.run()