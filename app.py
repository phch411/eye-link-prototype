import streamlit as st
from supabase import create_client
import pandas as pd
import requests
import streamlit.components.v1 as components
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Eye-Link", layout="wide")

# --- 1. 데이터베이스 관리 클래스 (Model) ---
class EyeLinkDB:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
        except Exception as e:
            st.error("설정 오류: Secrets를 확인해주세요.")

    def authenticate(self, u_id, pw):
        try:
            res = self.client.table("users").select("*").eq("school_id", u_id.strip()).execute()
            if res.data and str(res.data[0]['password']).strip() == str(pw).strip():
                return [res.data[0]]
            return []
        except: return []

    def fetch_students(self, school_id):
        try:
            q = self.client.table("students").select("*").eq("school_id", school_id).order("student_name").execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

    def update_student_status(self, s_name, status):
        """[해결] 파이썬 문법에 맞게 ID 생성 및 상태 업데이트 로직 수정"""
        try:
            # 자바스크립트 로직과 동일한 결과가 나오도록 파이썬으로 구현
            student_id = int(abs(sum(ord(c) for c in s_name) % 1000000))
            self.client.table("students").update({"status": status}).eq("id", student_id).execute()
        except: pass

# --- 2. UI 및 로직 제어 클래스 (View/Controller) ---
class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'user_info' not in st.session_state: st.session_state['user_info'] = None
        if 'selected_student_id' not in st.session_state: st.session_state['selected_student_id'] = None
        if 'tracking_active' not in st.session_state: st.session_state['tracking_active'] = False

    def show_login_page(self):
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.title("🛡️ Eye-Link")
            with st.container(border=True):
                u_id = st.text_input("아이디 (school_id)")
                u_pw = st.text_input("비밀번호", type="password")
                if st.button("로그인", use_container_width=True):
                    user = self.db.authenticate(u_id, u_pw)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = user[0]
                        st.rerun()
                    else: st.error("정보를 확인해주세요.")

    def show_dashboard(self):
        user = st.session_state['user_info']
        st.sidebar.title(f"🏫 {user['school_name']}")
        
        df_students = self.db.fetch_students(user['school_id'])
        menu = st.sidebar.radio("관리 메뉴", ["실시간 학생 모니터링", "학생 위치 전송 시스템"])
        
        if st.sidebar.button("로그아웃"): 
            st.session_state['logged_in'] = False
            st.rerun()

        if menu == "실시간 학생 모니터링":
            self.page_monitoring(df_students)
        elif menu == "학생 위치 전송 시스템":
            self.page_sender(user['school_id'])

    def page_monitoring(self, df_students):
        st.title("👁️ 실시간 학생 모니터링")
        if not df_students.empty:
            c1, c2 = st.columns([1, 3])
            with c1:
                st.subheader("👤 명단")
                for _, row in df_students.iterrows():
                    status_icon = "🟢" if row.get('status') == "전송중" else "🔴"
                    if st.button(f"{status_icon} {row['student_name']}", key=f"s_{row['id']}", use_container_width=True):
                        st.session_state['selected_student_id'] = row['id']
                        st.rerun()
            with c2:
                selected_id = st.session_state.get('selected_student_id')
                is_active = False
                lat, lon = 35.8714, 128.6014 # 기본 좌표
                
                if selected_id:
                    selected_row = df_students[df_students['id'] == selected_id].iloc[0]
                    is_active = (selected_row['status'] == "전송중")
                    lat, lon = selected_row['lat'], selected_row['lon']
                
                # [해결] 파란색 마커가 겹치지 않도록 is_active 상태 전달
                self.render_kakao_map(lat, lon, is_active)
        else: st.info("데이터가 없습니다.")

    def page_sender(self, school_id):
        st.title("📲 학생 위치 전송 시스템")
        with st.container(border=True):
            s_name = st.text_input("학생 이름 입력", placeholder="이름을 입력하세요.")
            col1, col2 = st.columns(2)
            
            if col1.button("🚀 위치 전송 시작", use_container_width=True, type="primary"):
                if s_name:
                    st.session_state['tracking_active'] = True
                    st.session_state['current_name'] = s_name
                    st.success(f"{s_name} 학생 전송 시작!")
                else: st.warning("이름을 입력해주세요.")
            
            if col2.button("⏹️ 전송 중지", use_container_width=True):
                if st.session_state.get('current_name'):
                    # 파이썬 로직으로 상태 즉시 업데이트 (빨간불 변경)
                    self.db.update_student_status(st.session_state['current_name'], "중단")
                    st.session_state['tracking_active'] = False
                    st.rerun()

            if st.session_state['tracking_active']:
                self.render_gps_sender(st.session_state['current_name'], school_id)

    def render_gps_sender(self, s_name, school_id):
        url, key = st.secrets["supabase"]["url"], st.secrets["supabase"]["key"]
        gps_js = f"""
        <script>
        const sUrl = "{url}", sKey = "{key}", schoolId = "{school_id}", sName = "{s_name}";
        const studentId = parseInt(Math.abs(sName.split('').reduce((a,b)=>{{a=((a<<5)-a)+b.charCodeAt(0);return a&a}},0) % 1000000));

        async function push() {{
            navigator.geolocation.getCurrentPosition(async (pos) => {{
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                const now = new Date().toISOString();

                await fetch(sUrl + "/rest/v1/students", {{
                    method: "POST",
                    headers: {{ "apikey": sKey, "Authorization": "Bearer "+sKey, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates" }},
                    body: JSON.stringify({{ id: studentId, student_name: sName, school_id: schoolId, status: "전송중", lat: lat, lon: lon, last_updated: now }})
                }});
            }}, null, {{ enableHighAccuracy: true }});
        }}
        setInterval(push, 10000); push();
        </script>
        <div style="padding:15px; background:#e8f5e9; border-radius:10px; text-align:center; border: 1px solid #c8e6c9;">
            <b style="color:#2e7d32;">🛰️ {s_name} 학생 실시간 위치 전송 중...</b>
        </div>
        """
        components.html(gps_js, height=100)

    def render_kakao_map(self, lat, lon, is_active):
        kakao_key = st.secrets['kakao']['js_key']
        
        # [해결] 파란색 마커 제거 로직: 실시간일 땐 CustomOverlay만, 중단 시에만 Marker 표시
        marker_script = ""
        if is_active:
            marker_script = f"""
            var content = '<div class="pulse-marker"></div>';
            new kakao.maps.CustomOverlay({{ position: new kakao.maps.LatLng({lat}, {lon}), content: content, map: map, yAnchor: 0.5 }});
            """
        else:
            marker_script = f"new kakao.maps.Marker({{ position: new kakao.maps.LatLng({lat}, {lon}), map: map }});"

        map_html = f"""
        <html>
        <head>
            <style>
                #map {{ width: 100%; height: 600px; border-radius: 15px; background: #eee; }}
                .pulse-marker {{ width: 22px; height: 22px; background: red; border: 3px solid white; border-radius: 50%; box-shadow: 0 0 12px rgba(255,0,0,0.8); animation: pulse 1.2s infinite; }}
                @keyframes pulse {{ 0% {{ transform: scale(0.8); opacity: 1; }} 70% {{ transform: scale(1.3); opacity: 0.4; }} 100% {{ transform: scale(0.8); opacity: 1; }} }}
            </style>
        </head>
        <body style="margin:0;"><div id="map"></div>
            <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&autoload=false"></script>
            <script>
                function init() {{
                    if (typeof kakao === 'undefined' || !kakao.maps) {{ setTimeout(init, 100); return; }}
                    kakao.maps.load(function() {{
                        var map = new kakao.maps.Map(document.getElementById('map'), {{ center: new kakao.maps.LatLng({lat}, {lon}), level: 3 }});
                        {marker_script}
                    }});
                }}
                init();
            </script>
        </body></html>
        """
        components.html(map_html, height=620)

# --- 3. 실행 ---
if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state.get('logged_in'): app.show_dashboard()
    else: app.show_login_page()