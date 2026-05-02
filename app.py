import streamlit as st
from supabase import create_client
import pandas as pd
import streamlit.components.v1 as components
import hashlib # 고유 번호 생성을 위한 해시 라이브러리

# 1. 페이지 설정
st.set_page_config(page_title="Eye-Link", layout="wide")

class EyeLinkDB:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
        except:
            st.error("Secrets 설정을 확인해주세요.")

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

    def fetch_location_logs(self, student_id):
        """[수정] 자동 생성된 고유 번호(student_id)를 기준으로 로그를 가져옵니다."""
        try:
            res = self.client.table("location_logs")\
                .select("created_at, lat, lon")\
                .eq("student_id", str(student_id))\
                .order("created_at", desc=True)\
                .limit(50)\
                .execute()
            df = pd.DataFrame(res.data)
            if not df.empty:
                df.columns = ['시간', '위도', '경도']
            return df
        except: return pd.DataFrame()

class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'user_info' not in st.session_state: st.session_state['user_info'] = None
        if 'selected_student_id' not in st.session_state: st.session_state['selected_student_id'] = None
        if 'selected_student_name' not in st.session_state: st.session_state['selected_student_name'] = None
        if 'tracking_active' not in st.session_state: st.session_state['tracking_active'] = False

    def show_login_page(self):
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.title("🛡️ Eye-Link 로그인")
            u_id = st.text_input("학교 아이디")
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
        menu = st.sidebar.radio("관리 메뉴", ["실시간 학생 모니터링", "학생 위치 전송 시스템"])
        
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()

        if menu == "실시간 학생 모니터링":
            st.title("👁️ 실시간 학생 모니터링")
            df_s = self.db.fetch_students(user['school_id'])
            if not df_s.empty:
                c1, c2 = st.columns([1, 3])
                with c1:
                    st.subheader("👤 명단")
                    for _, row in df_s.iterrows():
                        # 학생 이름 클릭 시 student_id를 세션에 저장
                        if st.button(f"📍 {row['student_name']}", key=f"btn_{row['id']}", use_container_width=True):
                            st.session_state['selected_student_id'] = row['id']
                            st.session_state['selected_student_name'] = row['student_name']
                            st.rerun()
                with c2:
                    logs_df = pd.DataFrame()
                    if st.session_state['selected_student_id']:
                        logs_df = self.db.fetch_location_logs(st.session_state['selected_student_id'])
                    self.render_kakao_map(df_s, logs_df)
            else: st.info("등록된 학생이 없습니다.")

        elif menu == "학생 위치 전송 시스템":
            st.title("📲 학생 위치 전송 시스템")
            with st.container(border=True):
                s_name = st.text_input("학생 이름 입력", placeholder="이름을 입력하세요")
                
                if st.button("🚀 위치 전송 시작", use_container_width=True, type="primary"):
                    if s_name:
                        st.session_state['tracking_active'] = True
                        st.success(f"{s_name} 학생 전송 시작!")
                    else: st.warning("이름을 입력해주세요.")
                
                if st.button("⏹️ 전송 중지", use_container_width=True):
                    st.session_state['tracking_active'] = False
                    st.rerun()

                if st.session_state['tracking_active']:
                    self.render_gps_sender(s_name)

    def render_gps_sender(self, s_name):
        s_url = st.secrets["supabase"]["url"]
        s_key = st.secrets["supabase"]["key"]
        
        # [핵심 로직] 이름 + 브라우저 정보를 조합해 6자리 고유번호 자동 생성 (JS 버전)
        gps_js = f"""
        <script>
        // 고유 식별자 생성 함수 (브라우저 지문 활용)
        function generateId(name) {{
            const agent = window.navigator.userAgent;
            const screen = window.screen.width + "x" + window.screen.height;
            const str = name + agent + screen;
            let hash = 0;
            for (let i = 0; i < str.length; i++) {{
                hash = ((hash << 5) - hash) + str.charCodeAt(i);
                hash |= 0;
            }}
            return Math.abs(hash % 1000000).toString().padStart(6, '0');
        }}

        const autoId = generateId("{s_name}");

        function sendLoc() {{
            if (navigator.geolocation) {{
                navigator.geolocation.getCurrentPosition((pos) => {{
                    fetch("{s_url}/rest/v1/location_logs", {{
                        method: 'POST',
                        headers: {{ 'apikey': "{s_key}", 'Authorization': 'Bearer {s_key}', 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            student_id: autoId,
                            student_name: "{s_name}",
                            lat: pos.coords.latitude,
                            lon: pos.coords.longitude,
                            created_at: new Date().toISOString()
                        }})
                    }});
                }});
            }}
        }}
        sendLoc();
        setInterval(sendLoc, 10000);
        </script>
        <div style="text-align:center; padding:15px; background:#e3f2fd; border-radius:10px; border: 1px solid #90caf9;">
            <h4 style="color:#0d47a1; margin-bottom:5px;">🛰️ {s_name} 학생 실시간 전송 중</h4>
            <code style="background:#fff; padding:2px 5px; border-radius:3px;">자동 생성 ID: #</code><span id="display-id" style="font-weight:bold;"></span>
            <script>document.getElementById('display-id').innerText = generateId("{s_name}");</script>
        </div>
        """
        components.html(gps_js, height=120)

    def render_kakao_map(self, df_students, logs_df):
        if df_students.empty: return
        lat, lon = (logs_df.iloc[0]['위도'], logs_df.iloc[0]['경도']) if not logs_df.empty else (df_students.iloc[0]['lat'], df_students.iloc[0]['lon'])
        kakao_key = st.secrets['kakao']['js_key']
        
        path_js, blink_js = "", ""
        if not logs_df.empty:
            for i, r in logs_df.iterrows():
                opacity = max(0.2, 1.0 - (i * 0.05))
                if i == 0:
                    blink_js = f"var content = '<div class=\"pulse-marker\"></div>'; new kakao.maps.CustomOverlay({{position:new kakao.maps.LatLng({r['위도']},{r['경도']}), content:content, map:map}});"
                else:
                    path_js += f"new kakao.maps.Circle({{map:map, center:new kakao.maps.LatLng({r['위도']},{r['경도']}), radius:4, fillColor:'#FF0000', fillOpacity:{opacity}, strokeWeight:0}});"

        map_html = f"""
        <html>
        <head>
            <style>
                #map {{ width: 100%; height: 600px; border-radius: 15px; }}
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
        <body>
            <div id="map"></div>
            <script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&autoload=false"></script>
            <script>
                function init() {{
                    kakao.maps.load(function() {{
                        var map = new kakao.maps.Map(document.getElementById('map'), {{center:new kakao.maps.LatLng({lat},{lon}), level:3}});
                        {path_js} {blink_js}
                    }});
                }}
                setTimeout(init, 100);
            </script>
        </body>
        </html>
        """
        components.html(map_html, height=620)

if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state.get('logged_in'): app.show_dashboard()
    else: app.show_login_page()