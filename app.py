import streamlit as st
from supabase import create_client
import pandas as pd
import re
import requests
import streamlit.components.v1 as components
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Eye-Link", layout="wide")

# 2. 데이터베이스 및 클래스 정의 (생략된 부분은 기존과 동일)
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
            q = self.client.table("user").select("*").eq("school_id", u_id).eq("password", pw).execute()
            return q.data
        except: return []

    def fetch_students(self, school_id):
        try:
            q = self.client.table("students").select("*").eq("school_id", school_id).execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

    def fetch_location_logs(self, student_id):
        """특정 학생의 로그만 정확히 필터링"""
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

class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'user_info' not in st.session_state: st.session_state['user_info'] = None
        if 'selected_student_id' not in st.session_state: st.session_state['selected_student_id'] = None
        if 'selected_student_name' not in st.session_state: st.session_state['selected_student_name'] = None

    def show_dashboard(self):
        user = st.session_state['user_info']
        st.sidebar.title(f"🏫 {user['school_name']}")
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()

        df_students = self.db.fetch_students(user['school_id'])

        st.title("👁️ 실시간 학생 모니터링")
        col_list, col_map = st.columns([1, 3])

        with col_list:
            st.subheader("👤 학생 명단")
            for _, row in df_students.iterrows():
                status_icon = "🟢" if row.get('status') == "정상" else "🔴"
                if st.button(f"{status_icon} {row['student_name']}", key=f"btn_{row['id']}", use_container_width=True):
                    st.session_state['selected_student_id'] = row['id']
                    st.session_state['selected_student_name'] = row['student_name']
                    st.rerun()

        with col_map:
            logs_df = pd.DataFrame()
            if st.session_state['selected_student_id']:
                logs_df = self.db.fetch_location_logs(st.session_state['selected_student_id'])
            self.render_kakao_map(df_students, logs_df)

    def render_kakao_map(self, df_students, logs_df):
        if df_students.empty: return
        
        # 1. 중심점 설정 (선택된 학생의 최신 로그 우선, 없으면 첫 번째 학생)
        if not logs_df.empty:
            lat, lon = logs_df.iloc[0]['위도'], logs_df.iloc[0]['경도']
        else:
            lat, lon = df_students.iloc[0]['lat'], df_students.iloc[0]['lon']

        kakao_key = st.secrets['kakao']['js_key']
        
        # 2. 다른 학생들 마커 (선택되지 않은 학생)
        other_markers_js = ""
        for _, r in df_students.iterrows():
            if str(r['id']) != str(st.session_state.get('selected_student_id')):
                other_markers_js += f"""
                new kakao.maps.Marker({{
                    map: map,
                    position: new kakao.maps.LatLng({r['lat']}, {r['lon']}),
                    title: '{r['student_name']}'
                }});
                """

        # 3. 선택된 학생의 동선 및 깜빡이는 현재 위치
        path_js = ""
        blink_overlay_js = ""
        
        if not logs_df.empty:
            for i, r in logs_df.iterrows():
                # [순서 표시] 과거로 갈수록 점이 작아지고 흐려짐
                opacity = max(0.2, 1.0 - (i * 0.05))
                radius = max(2, 6 - (i * 0.2))
                
                if i == 0: # 최신 위치: 카카오맵 CustomOverlay로 깜빡임 구현
                    blink_overlay_js = f"""
                    var content = '<div class="pulse-marker"></div>';
                    var customOverlay = new kakao.maps.CustomOverlay({{
                        position: new kakao.maps.LatLng({r['위도']}, {r['경도']}),
                        content: content,
                        yAnchor: 0.5
                    }});
                    customOverlay.setMap(map);
                    """
                else: # 과거 이동 동선 (빨간 점들)
                    path_js += f"""
                    new kakao.maps.Circle({{
                        map: map,
                        center: new kakao.maps.LatLng({r['위도']}, {r['경도']}),
                        radius: {radius},
                        strokeWeight: 0,
                        fillColor: '#FF0000',
                        fillOpacity: {opacity}
                    }});
                    """

        map_html = f"""
        <html>
        <head>
            <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
            <style>
                #map {{ width: 100%; height: 650px; border-radius: 15px; }}
                /* 깜빡이는 애니메이션 정의 */
                .pulse-marker {{
                    width: 16px;
                    height: 16px;
                    background-color: #FF0000;
                    border: 3px solid #FFFFFF;
                    border-radius: 50%;
                    box-shadow: 0 0 0 rgba(255, 0, 0, 0.4);
                    animation: pulse 1.5s infinite;
                }}
                @keyframes pulse {{
                    0% {{ box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.7); }}
                    70% {{ box-shadow: 0 0 0 15px rgba(255, 0, 0, 0); }}
                    100% {{ box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }}
                }}
            </style>
        </head>
        <body style="margin:0;">
            <div id="map"></div>
            <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&autoload=false"></script>
            <script>
                function initMap() {{
                    if (typeof kakao === 'undefined' || !kakao.maps) {{
                        setTimeout(initMap, 100);
                        return;
                    }}
                    kakao.maps.load(function() {{
                        var container = document.getElementById('map');
                        var options = {{
                            center: new kakao.maps.LatLng({lat}, {lon}),
                            level: 3
                        }};
                        var map = new kakao.maps.Map(container, options);
                        
                        {other_markers_js}
                        {path_js}
                        {blink_overlay_js}
                    }});
                }}
                initMap();
            </script>
        </body>
        </html>
        """
        components.html(map_html, height=670)

# 실행부 생략 (동일)
if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state.get('logged_in'): app.show_dashboard()
    else: app.show_login_page()