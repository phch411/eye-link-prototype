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

    def authenticate(self, u_id, pw):
        try:
            q = self.client.table("users").select("*").eq("school_id", u_id).eq("password", pw).execute()
            return q.data
        except: return []

    def fetch_students(self, school_id):
        try:
            q = self.client.table("students").select("*").eq("school_id", school_id).execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

# --- 2. UI 및 로직 제어 클래스 (View) ---
class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'show_signup' not in st.session_state: st.session_state['show_signup'] = False
        if 'user_info' not in st.session_state: st.session_state['user_info'] = None

    def show_login_page(self):
        """감성적인 문구가 적용된 첫 화면"""
        _, col, _ = st.columns([1, 1.5, 1])
        
        with col:
            st.write("") # 상단 여백
            st.write("")
            st.title("🛡️ Eye-Link")
            
            # [수정] 딱딱한 문구를 지우고 감성적인 문구 추가
            st.markdown("""
                ### **아이들의 발걸음이 언제나 안녕하기를**  
                
                가장 따뜻한 시선으로 아이들의 소중한 발걸음을 함께 지킵니다.
            """)
            st.write("") # 간격 조절
            
            with st.container(border=True):
                u_id = st.text_input("아이디 (ID)", placeholder="학교 아이디를 입력하세요")
                u_pw = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
                
                if st.button("함께하기", use_container_width=True): # 버튼 문구도 변경
                    user = self.db.authenticate(u_id, u_pw)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = user[0]
                        st.rerun()
                    else:
                        st.error("아이디 또는 비밀번호를 다시 확인해 주세요.")
                
                st.write("---")
                if st.button("우리 학교 등록하기", use_container_width=True):
                    st.session_state['show_signup'] = True
                    st.rerun()

    def show_dashboard(self):
        """카카오맵이 적용된 실시간 모니터링 대시보드"""
        user = st.session_state['user_info']
        st.sidebar.title(f"🏫 {user['school_name']}")
        
        menu = st.sidebar.radio("관리 메뉴", ["실시간 학생 모니터링", "학생별 상황", "사전 위험구간 설정"])
        st.sidebar.divider()
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
                        st.caption(f"최근 갱신: {row.get('updated_at', '정보없음')}")
                with col_map:
                    # 카카오맵 렌더링 (이전 답변 드린 render_kakao_map 로직 사용)
                    self.render_kakao_map(df)
            else:
                st.info("현재 등록된 학생 위치 데이터가 없습니다.")

    def render_kakao_map(self, df):
        """카카오맵 렌더링 (JS Key 필요)"""
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
        # 이전 답변의 회원가입 페이지 함수 호출
        st.write("회원가입 페이지") 
    else:
        app.show_login_page()