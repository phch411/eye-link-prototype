import streamlit as st
from supabase import create_client
import pandas as pd
import re
import requests
import streamlit.components.v1 as components

# [필수] 1순위: 페이지 설정
st.set_page_config(page_title="Eye-Link", layout="wide")

# --- 1. 데이터베이스 관리 클래스 (Model) ---
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
        """나이스 API 학교 검색"""
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
        """회원가입 실행"""
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

# --- 2. UI 및 로직 제어 클래스 (View/Controller) ---
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
        """감성적인 첫 화면"""
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.write("")
            st.write("")
            st.title("🛡️ Eye-Link")
            st.markdown("""
                ### **아이들의 발걸음이**  
                ### **언제나 안녕하기를.**
                
                가장 따뜻한 시선으로  
                아이들의 소중한 등하굣길을 함께 지킵니다.
            """)
            st.write("")
            with st.container(border=True):
                u_id = st.text_input("아이디 (ID)", placeholder="학교 아이디를 입력하세요")
                u_pw = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
                if st.button("함께하기", use_container_width=True):
                    user = self.db.authenticate(u_id, u_pw)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = user[0]
                        st.rerun()
                    else: st.error("아이디 또는 비밀번호를 다시 확인해 주세요.")
                st.write("---")
                if st.button("우리 학교 등록하기", use_container_width=True):
                    st.session_state['show_signup'] = True
                    st.rerun()

    def show_signup_page(self):
        """[핵심] 학교 등록(회원가입) 페이지"""
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.title("📝 학교 가입")
            with st.container(border=True):
                s_input = st.text_input("1. 학교명 검색 (2글자 이상 입력)")
                selected_school = None
                
                if len(s_input) >= 2:
                    school_list = self.db.get_school_list(s_input)
                    if school_list:
                        opts = {f"{s['SCHUL_NM']} ({s['ORG_RDNMA']})": s for s in school_list}
                        choice = st.selectbox("2. 학교 선택", options=["선택하세요"] + list(opts.keys()))
                        if choice != "선택하세요":
                            selected_school = opts[choice]
                    else: st.warning("검색 결과가 없습니다.")

                if selected_school:
                    st.divider()
                    s_name, s_addr = selected_school['SCHUL_NM'], selected_school['ORG_RDNMA']
                    st.info(f"📍 선택된 학교: {s_name}")
                    
                    u_id = st.text_input("3. 사용할 학교 관리자 ID")
                    pw = st.text_input("4. 비밀번호 설정", type="password")
                    is_v, msg = self.validate_pw(pw)
                    if pw:
                        if is_v: st.success(msg)
                        else: st.error(msg)
                    
                    pw_c = st.text_input("5. 비밀번호 확인", type="password")
                    
                    if st.button("가입 완료", use_container_width=True):
                        if u_id and is_v and pw == pw_c:
                            ok, res = self.db.register(u_id, pw, s_name, s_addr)
                            if ok:
                                st.success(res)
                                st.balloons()
                                st.session_state['show_signup'] = False
                                st.rerun()
                            else: st.error(res)
                        else: st.warning("입력 정보를 다시 확인해 주세요.")
            
            if st.button("이전으로 돌아가기"):
                st.session_state['show_signup'] = False
                st.rerun()

    def show_dashboard(self):
        """실시간 모니터링 대시보드"""
        user = st.session_state['user_info']
        st.sidebar.title(f"🏫 {user['school_name']}")
        menu = st.sidebar.radio("관리 메뉴", ["실시간 학생 모니터링", "학생별 상황", "사전 위험구간 설정"])
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()

        df = self.db.fetch_students(user['school_id'])

        if menu == "실시간 학생 모니터링":
            st.title("👁️ 실시간 학생 모니터링")
            if not df.empty:
                col_list, col_map = st.columns([1, 3])
                with col_list:
                    st.subheader("👤 명단")
                    for _, row in df.iterrows():
                        st.write(f"🟢 **{row['student_name']}**")
                with col_map:
                    self.render_kakao_map(df)
            else:
                st.info("데이터가 없습니다. GPS 기기를 켜주세요.")

    def render_kakao_map(self, df):
        lat, lon = df.iloc[0]['lat'], df.iloc[0]['lon']
        markers = ""
        for _, r in df.iterrows():
            markers += f"new kakao.maps.Marker({{map:map, position:new kakao.maps.LatLng({r['lat']},{r['lon']}), title:'{r['student_name']}'}});"

        map_html = f"""
        <div id="map" style="width:100%;height:500px;border-radius:15px;"></div>
        <script type="text/javascript" src="//dapi.kakao.com/v2/maps/sdk.js?appkey={st.secrets['kakao']['js_key']}"></script>
        <script>
            var container = document.getElementById('map');
            var options = {{ center: new kakao.maps.LatLng({lat}, {lon}), level: 3 }};
            var map = new kakao.maps.Map(container, options);
            {markers}
        </script>
        """
        components.html(map_html, height=520)

# --- 3. 실행부 ---
if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state['logged_in']:
        app.show_dashboard()
    elif st.session_state['show_signup']:
        app.show_signup_page() # 이제 이 함수가 정상 작동합니다!
    else:
        app.show_login_page()