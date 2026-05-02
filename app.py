import streamlit as st
from supabase import create_client
import pandas as pd
import re
import requests
import streamlit.components.v1 as components
from datetime import datetime

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
        """users 테이블에서 인증 (관리자 로그인)"""
        try:
            q = self.client.table("users").select("*").eq("school_id", u_id).eq("password", pw).execute()
            return q.data
        except: return []

    def fetch_students(self, school_id):
        """students 테이블에서 목록 가져오기"""
        try:
            q = self.client.table("students").select("*").eq("school_id", school_id).execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

    def fetch_location_logs(self, student_id):
        """특정 학생의 10초 단위 위치 로그 가져오기"""
        try:
            res = self.client.table("location_logs")\
                .select("created_at, lat, lon")\
                .eq("student_id", str(student_id))\
                .order("created_at", desc=True)\
                .limit(50)\
                .execute()
            df = pd.DataFrame(res.data)
            if not df.empty:
                df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%H:%M:%S')
                df.columns = ['시간', '위도', '경도']
            return df
        except: return pd.DataFrame()

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
            st.title("🛡️ Eye-Link 로그인")
            st.markdown("### **아이들의 발걸음을 지키는 따뜻한 시선**")
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

    def show_dashboard(self):
        user = st.session_state['user_info']
        
        # --- 사이드바 메뉴 구성 ---
        st.sidebar.title(f"🏫 {user['school_name']}")
        menu = st.sidebar.radio(
            "관리 메뉴", 
            ["실시간 학생 모니터링", "학생 위치 전송 시스템", "학생별 상황", "사전 위험구간 설정"]
        )
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()

        # --- [기능 1] 실시간 학생 모니터링 ---
        if menu == "실시간 학생 모니터링":
            st.title("👁️ 실시간 학생 모니터링")
            df_s = self.db.fetch_students(user['school_id'])
            
            if not df_s.empty:
                c1, c2 = st.columns([1, 3])
                with c1:
                    st.subheader("👤 학생 명단")
                    for _, row in df_s.iterrows():
                        status_icon = "🟢" if row.get('status') == "정상" else "🔴"
                        if st.button(f"{status_icon} {row['student_name']}", key=f"btn_{row['id']}", use_container_width=True):
                            st.session_state['selected_student_id'] = row['id']
                            st.session_state['selected_student_name'] = row['student_name']
                            st.rerun()
                with c2:
                    logs_df = pd.DataFrame()
                    if st.session_state['selected_student_id']:
                        logs_df = self.db.fetch_location_logs(st.session_state['selected_student_id'])
                    self.render_kakao_map(df_s, logs_df)
            else:
                st.info("등록된 학생 데이터가 없습니다.")

        # --- [기능 2] 학생 위치 전송 시스템 (Netlify 기능 이식) ---
        elif menu == "학생 위치 전송 시스템":
            st.title("📲 학생 위치 전송 시스템")
            st.info("학생용 모바일 기기에서 사용하세요. 10초마다 자동으로 위치를 전송합니다.")
            
            with st.container(border=True):
                s_name = st.text_input("학생 이름 입력", placeholder="예: 홍길동")
                s_id = st.text_input("학생 고유 ID 입력", placeholder="예: 1001")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🚀 위치 전송 시작", use_container_width=True, type="primary"):
                        if s_name and s_id:
                            st.session_state['tracking_active'] = True
                            st.success(f"{s_name} 학생 위치 전송 시작!")
                        else: st.warning("이름과 ID를 입력하세요.")
                with col2:
                    if st.button("⏹️ 전송 중지", use_container_width=True):
                        st.session_state['tracking_active'] = False
                        st.info("전송이 중지되었습니다.")

                if st.session_state['tracking_active']:
                    self.render_gps_sender(s_id, s_name)

        # --- 나머지 준비 중 메뉴 ---
        else:
            st.title(f"📂 {menu}")
            st.write("본 기능은 현재 개발 및 준비 중입니다.")

    def render_gps_sender(self, s_id, s_name):
        """브라우저 GPS 정보를 수파베이스로 전송하는 JavaScript 이식"""
        s_url = st.secrets["supabase"]["url"]
        s_key = st.secrets["supabase"]["key"]
        
        gps_js = f"""
        <script>
        const studentId = "{s_id}";
        const studentName = "{s_name}";
        const endpoint = "{s_url}/rest/v1/location_logs";
        const apiKey = "{s_key}";

        function sendLoc() {{
            if (navigator.geolocation) {{
                navigator.geolocation.getCurrentPosition((pos) => {{
                    const payload = {{
                        student_id: studentId,
                        student_name: studentName,
                        lat: pos.coords.latitude,
                        lon: pos.coords.longitude,
                        created_at: new Date().toISOString()
                    }};
                    fetch(endpoint, {{
                        method: 'POST',
                        headers: {{ 'apikey': apiKey, 'Authorization': 'Bearer ' + apiKey, 'Content-Type': 'application/json' }},
                        body: JSON.stringify(payload)
                    }});
                }});
            }}
        }}
        sendLoc();
        setInterval(sendLoc, 10000); // 10초 주기
        </script>
        <div style="text-align:center; padding:20px; background:#e3f2fd; border-radius:10px;">
            <h4 style="color:#0d47a1; margin:0;">🛰️ 실시간 GPS 전송 중...</h4>
            <p style="font-size:0.8rem; color:#1565c0;">이 화면을 유지해 주세요.</p>
        </div>
        """
        components.html(gps_js, height=150)

    def render_kakao_map(self, df_students, logs_df):
        """지도 렌더링: 깜빡이는 빨간 원 효과 포함"""
        if df_students.empty: return
        lat, lon = (logs_df.iloc[0]['위도'], logs_df.iloc[0]['경도']) if not logs_df.empty else (df_students.iloc[0]['lat'], df_students.iloc[0]['lon'])
        kakao_key = st.secrets['kakao']['js_key']
        
        others_js = ""
        for _, r in df_students.iterrows():
            if str(r['id']) != str(st.session_state.get('selected_student_id')):
                others_js += f"new kakao.maps.Marker({{map:map, position:new kakao.maps.LatLng({r['lat']},{r['lon']})}});"

        path_js, blink_js = "", ""
        if not logs_df.empty:
            for i, r in logs_df.iterrows():
                opacity = max(0.2, 1.0 - (i * 0.05))
                if i == 0:
                    blink_js = f"""
                    var content = '<div class="pulse-marker"></div>';
                    new kakao.maps.CustomOverlay({{position:new kakao.maps.LatLng({r['위도']},{r['경도']}), content:content, map:map}});
                    """
                else:
                    path_js += f"new kakao.maps.Circle({{map:map, center:new kakao.maps.LatLng({r['위도']},{r['경도']}), radius:4, fillColor:'#FF0000', fillOpacity:{opacity}, strokeWeight:0}});"

        map_html = f"""
        <html>
        <head>
            <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
            <style>
                #map {{ width: 100%; height: 650px; border-radius: 15px; }}
                .pulse-marker {{
                    width: 18px; height: 18px; background: #FF0000; border: 3px solid #FFF; border-radius: 50%;
                    box-shadow: 0 0 10px rgba(255,0,0,0.7); animation: pulse 1.5s infinite;
                }}
                @keyframes pulse {{
                    0% {{ transform: scale(0.9); box-shadow: 0 0 0 0 rgba(255,0,0,0.7); }}
                    70% {{ transform: scale(1.1); box-shadow: 0 0 0 15px rgba(255,0,0,0); }}
                    100% {{ transform: scale(0.9); box-shadow: 0 0 0 0 rgba(255,0,0,0); }}
                }}
            </style>
        </head>
        <body style="margin:0;"><div id="map"></div>
        <script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&autoload=false"></script>
        <script>
            function init() {{
                kakao.maps.load(function() {{
                    var map = new kakao.maps.Map(document.getElementById('map'), {{center:new kakao.maps.LatLng({lat},{lon}), level:3}});
                    {others_js} {path_js} {blink_js}
                }});
            }}
            setTimeout(init, 100);
        </script></body></html>
        """
        components.html(map_html, height=670)

# --- 3. 실행부 ---
if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state.get('logged_in'): app.show_dashboard()
    else: app.show_login_page()