import streamlit as st
from supabase import create_client
import pandas as pd
import requests
import streamlit.components.v1 as components
from datetime import datetime

# 1. 페이지 기본 설정
st.set_page_config(page_title="Eye-Link", layout="wide")

# --- 1. 데이터베이스 관리 (Model) ---
class EyeLinkDB:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
            self.neis_key = st.secrets["neis"]["api_key"]
        except Exception as e:
            st.error("설정 오류: Secrets를 확인해주세요.")

    def authenticate(self, u_id, pw):
        try:
            res = self.client.table("users").select("*").eq("school_id", u_id.strip()).execute()
            if res.data and str(res.data[0]['password']).strip() == str(pw).strip():
                return res.data[0]
            return None
        except: return None

    def get_school_list(self, keyword):
        url = "https://open.neis.go.kr/hub/schoolInfo"
        params = {"KEY": self.neis_key, "Type": "json", "pIndex": 1, "pSize": 10, "SCHUL_NM": keyword}
        try:
            res = requests.get(url, params=params).json()
            return res["schoolInfo"][1]["row"] if "schoolInfo" in res else []
        except: return []

# --- 2. 앱 UI 및 로직 (View/Controller) ---
class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'user_info' not in st.session_state: st.session_state['user_info'] = None
        if 'selected_student_id' not in st.session_state: st.session_state['selected_student_id'] = None

    def show_login_page(self):
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.title("🛡️ Eye-Link")
            with st.container(border=True):
                u_id = st.text_input("학교 ID")
                u_pw = st.text_input("비밀번호", type="password")
                if st.button("로그인", use_container_width=True):
                    user = self.db.authenticate(u_id, u_pw)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = user
                        st.rerun()
                    else: st.error("정보가 일치하지 않습니다.")

    def show_dashboard(self):
        user = st.session_state['user_info']
        st.sidebar.title(f"🏫 {user['school_name']}")
        
        menu = st.sidebar.radio("관리 메뉴", ["실시간 모니터링", "위험구역 설정", "학생 위치 전송"])
        if st.sidebar.button("로그아웃"): 
            st.session_state['logged_in'] = False
            st.rerun()

        if menu == "실시간 모니터링":
            self.page_monitoring(user['school_id'])
        elif menu == "위험구역 설정":
            self.page_danger_zone(user['school_id'])
        elif menu == "학생 위치 전송":
            self.page_sender(user['school_id'])

    # --- [페이지 1] 실시간 모니터링 ---
    def page_monitoring(self, school_id):
        st.title("👁️ 실시간 학생 모니터링")
        res = self.db.client.table("students").select("*").eq("school_id", school_id).execute()
        df = pd.DataFrame(res.data)

        if not df.empty:
            c1, c2 = st.columns([1, 3])
            with c1:
                st.subheader("👤 학생 명단")
                for _, row in df.iterrows():
                    icon = "🟢" if row['status'] == "전송중" else "🔴"
                    if st.button(f"{icon} {row['student_name']}", key=f"btn_{row['id']}", use_container_width=True):
                        st.session_state['selected_student_id'] = row['id']
                        st.rerun()
            
            with c2:
                selected_id = st.session_state.get('selected_student_id')
                logs = pd.DataFrame()
                if selected_id:
                    log_res = self.db.client.table("location_logs").select("*").eq("student_id", selected_id).order("created_at", desc=True).limit(1).execute()
                    logs = pd.DataFrame(log_res.data)
                
                dz_res = self.db.client.table("danger_zones").select("*").eq("school_id", school_id).execute()
                dz_df = pd.DataFrame(dz_res.data)
                
                self.render_kakao_map(df, logs, dz_df)
        else: st.info("등록된 데이터가 없습니다.")

    # --- [페이지 2] 위험구역 설정 ---
    def page_danger_zone(self, school_id):
        st.title("⚠️ 위험구역 설정")
        col1, col2 = st.columns([3, 1])
        
        # 학교 위치 (기본 좌표)
        school_lat, school_lon = 35.2332, 128.8819 

        with col2:
            st.subheader("구역 정보")
            z_name = st.text_input("구역 명칭", placeholder="예: 공사장")
            radius = st.radio("위험 반경(m)", [5, 10, 20], horizontal=True)
            if st.button("현재 위치 등록", use_container_width=True, type="primary"):
                self.db.client.table("danger_zones").insert({
                    "school_id": school_id, "zone_name": z_name, 
                    "lat": school_lat, "lon": school_lon, "radius": radius
                }).execute()
                st.success("등록 완료!")

        with col1:
            self.render_kakao_map(pd.DataFrame(), pd.DataFrame(), pd.DataFrame([{"lat": school_lat, "lon": school_lon, "radius": 0}]))

    # --- [페이지 3] 학생 위치 전송 ---
    def page_sender(self, school_id):
        st.title("📲 학생 위치 전송 시스템")
        name = st.text_input("학생 이름을 입력하세요")
        if name:
            self.render_gps_sender(name, school_id)

    # --- [컴포넌트] GPS 전송 (초기 안정 버전 복구) ---
    def render_gps_sender(self, s_name, school_id):
        url, key = st.secrets["supabase"]["url"], st.secrets["supabase"]["key"]
        gps_js = f"""
        <script>
        const sUrl = "{url}", sKey = "{key}", schoolId = "{school_id}", sName = "{s_name}";
        const studentId = parseInt(Math.abs(sName.split('').reduce((a,b)=>{{a=((a<<5)-a)+b.charCodeAt(0);return a&a}},0) % 1000000));
        
        async function send() {{
            navigator.geolocation.getCurrentPosition(async (pos) => {{
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                
                await fetch(sUrl + "/rest/v1/students", {{
                    method: "POST", headers: {{ "apikey": sKey, "Authorization": "Bearer "+sKey, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates" }},
                    body: JSON.stringify({{ id: studentId, student_name: sName, school_id: schoolId, status: "전송중", lat: lat, lon: lon }})
                }});
                await fetch(sUrl + "/rest/v1/location_logs", {{
                    method: "POST", headers: {{ "apikey": sKey, "Authorization": "Bearer "+sKey, "Content-Type": "application/json" }},
                    body: JSON.stringify({{ student_id: studentId, student_name: sName, lat: lat, lon: lon }})
                }});
            }}, null, {{ enableHighAccuracy: true }});
        }}
        setInterval(send, 10000); send();
        </script>
        <div style="padding:20px; background:#e8f5e9; border-radius:10px; text-align:center;">🛰️ <b>{s_name}</b> 학생 위치 전송 중입니다.</div>
        """
        components.html(gps_js, height=120)

    # --- [컴포넌트] 카카오맵 (지도 안 뜨는 문제 해결 버전) ---
    def render_kakao_map(self, df_students, logs_df, dz_df):
        kakao_key = st.secrets['kakao']['js_key']
        
        # 중심점 좌표 설정
        if not logs_df.empty:
            lat, lon = logs_df.iloc[0]['lat'], logs_df.iloc[0]['lon']
        elif not dz_df.empty:
            lat, lon = dz_df.iloc[0]['lat'], dz_df.iloc[0]['lon']
        else:
            lat, lon = 35.2332, 128.8819

        # 마커 및 원 스크립트
        js_draw = ""
        if not dz_df.empty:
            for _, dz in dz_df.iterrows():
                if dz['radius'] > 0:
                    js_draw += f"new kakao.maps.Circle({{ center: new kakao.maps.LatLng({dz['lat']}, {dz['lon']}), radius: {dz['radius']}, strokeWeight: 2, strokeColor: '#FF0000', strokeOpacity: 0.8, fillStyle: 'solid', fillColor: '#FF0000', fillOpacity: 0.3 }}).setMap(map);"
        
        if not df_students.empty:
            for _, s in df_students.iterrows():
                if s['lat'] != 0:
                    js_draw += f"new kakao.maps.Marker({{ position: new kakao.maps.LatLng({s['lat']}, {s['lon']}), map: map, title: '{s['student_name']}' }});"

        map_html = f"""
        <html>
        <head>
            <style> #map {{ width: 100%; height: 600px; border-radius: 15px; background: #eee; }} </style>
        </head>
        <body style="margin:0;"><div id="map"></div>
            <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&autoload=false"></script>
            <script>
                function loadMap() {{
                    if (typeof kakao === 'undefined' || !kakao.maps) {{ setTimeout(loadMap, 100); return; }}
                    kakao.maps.load(function() {{
                        var container = document.getElementById('map');
                        var options = {{ center: new kakao.maps.LatLng({lat}, {lon}), level: 3 }};
                        var map = new kakao.maps.Map(container, options);
                        {js_draw}
                    }});
                }}
                loadMap();
            </script>
        </body></html>
        """
        components.html(map_html, height=620)

# --- 3. 실행부 ---
if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state['logged_in']: app.show_dashboard()
    else: app.show_login_page()