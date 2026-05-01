import streamlit as st
from supabase import create_client
import pandas as pd
import re
import requests

# [필수] 1순위: 페이지 설정
st.set_page_config(page_title="Eye-Link 시스템", layout="wide")

# --- 1. 데이터베이스 및 API 관리 클래스 (Model) ---
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

    def fetch_students(self, school_id):
        try:
            q = self.client.table("students").select("*").eq("school_id", school_id).execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

# --- 2. UI 및 비즈니스 로직 제어 클래스 (Controller/View) ---
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
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
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
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.title("📝 학교 가입")
            with st.container(border=True):
                s_input = st.text_input("1. 학교명 검색 (2글자 이상)")
                selected_school = None
                if len(s_input) >= 2:
                    school_list = self.db.get_school_list(s_input)
                    if school_list:
                        opts = {f"{s['SCHUL_NM']} ({s['ORG_RDNMA']})": s for s in school_list}
                        choice = st.selectbox("2. 학교 선택", options=["선택하세요"] + list(opts.keys()))
                        if choice != "선택하세요": selected_school = opts[choice]
                    else: st.warning("검색 결과가 없습니다.")

                if selected_school:
                    st.divider()
                    s_name, s_addr = selected_school['SCHUL_NM'], selected_school['ORG_RDNMA']
                    st.info(f"📍 선택: {s_name}")
                    u_id = st.text_input("3. 아이디 설정")
                    pw = st.text_input("4. 비밀번호 설정", type="password")
                    is_v, msg = self.validate_pw(pw)
                    if pw:
                        if is_v: st.success(msg)
                        else: st.error(msg)
                    pw_c = st.text_input("5. 비밀번호 확인", type="password")
                    if st.button("가입 신청", use_container_width=True):
                        if u_id and is_v and pw == pw_c:
                            ok, res = self.db.register(u_id, pw, s_name, s_addr)
                            if ok:
                                st.success(res); st.balloons()
                                st.session_state['show_signup'] = False
                                st.rerun()
                            else: st.error(res)
            if st.button("이전으로"):
                st.session_state['show_signup'] = False
                st.rerun()

    def show_dashboard(self):
        """사이드바 메뉴 구성 및 화면 분기"""
        user = st.session_state['user_info']
        
        # --- 사이드바 구성 ---
        st.sidebar.title(f"🏫 {user['school_name']}")
        st.sidebar.write(f"ID: {user['school_id']}")
        st.sidebar.markdown("---")
        
        # [메뉴 추가] 3가지 핵심 메뉴 선택
        menu = st.sidebar.radio(
            "관리 메뉴",
            ["학생별 상황", "실시간 아동 모니터링", "사전 위험구간 설정"]
        )
        
        st.sidebar.markdown("---")
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()

        # --- 메뉴별 화면 렌더링 ---
        df = self.db.fetch_students(user['school_id'])

        if menu == "학생별 상황":
            st.title("👤 학생별 세부 상황")
            if not df.empty:
                # 학생 선택 셀렉트박스
                student_names = df['student_name'].tolist()
                selected_st = st.selectbox("조회할 학생을 선택하세요", student_names)
                
                st_info = df[df['student_name'] == selected_st].iloc[0]
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("현재 상태", st_info['status'])
                    st.write(f"최근 수신 시각: {st_info.get('updated_at', 'N/A')}")
                with col2:
                    st.write(f"현재 위도: {st_info['lat']}")
                    st.write(f"현재 경도: {st_info['lon']}")
                
                st.divider()
                st.subheader(f"{selected_st} 학생 현재 위치")
                st.map(df[df['student_name'] == selected_st])
            else:
                st.info("등록된 학생 데이터가 없습니다.")

        elif menu == "실시간 아동 모니터링":
            st.title("👁️ 실시간 아동 모니터링")
            if not df.empty:
                # 전체 지도 및 리스트
                st.map(df)
                st.subheader("전체 학생 위치 현황")
                st.dataframe(df, use_container_width=True)
            else:
                st.info("모니터링할 데이터가 없습니다.")

        elif menu == "사전 위험구간 설정":
            st.title("⚠️ 사전 위험구간 설정")
            st.info("학교 주변 통학로 중 주의가 필요한 구간(Geo-fence)을 설정하는 페이지입니다.")
            with st.expander("위험구간 등록하기"):
                zone_name = st.text_input("구간 명칭 (예: 정문 앞 사거리)")
                st.text_input("중심 위도")
                st.text_input("중심 경도")
                st.slider("감지 반경 (m)", 10, 500, 50)
                if st.button("구간 저장"):
                    st.success(f"'{zone_name}' 구간이 등록되었습니다.")

# --- 3. 실행부 ---
if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state['logged_in']: app.show_dashboard()
    elif st.session_state['show_signup']: app.show_signup_page()
    else: app.show_login_page()