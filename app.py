import streamlit as st
from supabase import create_client
import pandas as pd
import re
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
            self.neis_key = st.secrets["neis"]["api_key"]
        except Exception as e:
            st.error("설정 오류: Secrets를 확인해주세요.")

    def authenticate(self, u_id, pw):
        try:
            # user 테이블: school_id, password (image_a55f9e.png 반영)
            q = self.client.table("user").select("*").eq("school_id", u_id).eq("password", pw).execute()
            return q.data
        except: return []

    def fetch_students(self, school_id):
        try:
            # students 테이블: id(int8), student_name, lat, lon, status, school_id (image_a55cd9.png 반영)
            q = self.client.table("students").select("*").eq("school_id", school_id).execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

    def fetch_location_logs(self, student_id):
        """특정 학생의 로그만 정확히 필터링 (image_a55c7d.png 반영)"""
        try:
            # student_id가 text 타입이므로 비교 시 주의
            res = self.client.table("location_logs")\
                .select("created_at, lat, lon")\
                .eq("student_id", str(student_id))\
                .order("created_at", desc=True)\
                .limit(50)\
                .execute()
            df = pd.DataFrame(res.data)
            if not df.empty:
                df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%H:%M:%S')
                # 렌더링 함수에서 쓸 컬럼명 통일
                df.columns = ['시간', '위도', '경도']
            return df
        except: return pd.DataFrame()

# --- 2. UI 및 로직 제어 클래스 (View/Controller) ---
class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        # 세션 상태 초기화
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'user_info' not in st.session_state: st.session_state['user_info'] = None
        if 'selected_student_id' not in st.session_state: st.session_state['selected_student_id'] = None
        if 'selected_student_name' not in st.session_state: st.session_state['selected_student_name'] = None

    def show_login_page(self):
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.title("🛡️ Eye-Link 로그인")
            with st.container(border=True):
                u_id = st.text_input("학교 코드 (school_id)")
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
        st.sidebar.title(f"🏫 {user['school_name']}")
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()

        # 실시간 데이터 로드
        df_students = self.db.fetch_students(user['school_id'])

        st.title("👁️ 실시간 학생 모니터링")
        col_list, col_map = st.columns([1, 3])

        with col_list:
            st.subheader("👤 학생 명단")
            if not df_students.empty:
                for _, row in df_students.iterrows():
                    # status 컬럼 기반 아이콘 설정
                    status_icon = "🟢" if row.get('status') == "정상" else "🔴"
                    # 버튼 클릭 시 해당 학생 ID 저장
                    if st.button(f"{status_icon} {row['student_name']}", key=f"btn_{row['id']}", use_container_width=True):
                        st.session_state['selected_student_id'] = row['id']
                        st.session_state['selected_student_name'] = row['student_name']
                        st.rerun()
            else:
                st.info("데이터가 없습니다.")

        with col_map:
            logs_df = pd.DataFrame()
            if st.session_state['selected_student_id']:
                # 에러 방지: self.db를 통해 호출
                logs_df = self.db.fetch_location_logs(st.session_state['selected_student_id'])
            
            # 지도 렌더링 함수 호출
            self.render_kakao_map(df_students, logs_df)

    def render_kakao_map(self, df_students, logs_df):
        if df_students.empty: return
        
        # 중심점 설정 (로그가 있으면 최신 로그 위치, 없으면 첫 번째 학생 위치)
        if not logs_df.empty:
            lat, lon = logs_df.iloc[0]['위도'], logs_df.iloc[0]['경도']
        else:
            lat, lon = df_students.iloc[0]['lat'], df_students.iloc[0]['lon']

        kakao_key = st.secrets['kakao']['js_key']
        
        # 전체 학생 마커 (선택되지 않은 학생들)
        other_markers_js = ""
        for _, r in df_students.iterrows():
            if str(r['id']) != str(st.session_state.get('selected_student_id')):
                other_markers_js += f"new kakao.maps.Marker({{map:map, position:new kakao.maps.LatLng({r['lat']},{r['lon']}), title:'{r['student_name']}'}});"

        # 선택된 학생 동선 및 깜빡이는 현재 위치
        path_js = ""
        blink_js = ""
        if not logs_df.empty:
            for i, r in logs_df.iterrows():
                # 인덱스(i)가 0일수록 최신 데이터
                opacity = max(0.2, 1.0 - (i * 0.05))
                if i == 0:
                    blink_js = f"""
                    var content = '<div class="pulse-marker"></div>';
                    var overlay = new kakao.maps.CustomOverlay({{
                        position: new kakao.maps.LatLng({r['위도']}, {r['경도']}),
                        content: content, yAnchor: 0.5
                    }});
                    overlay.setMap(map);
                    """
                else:
                    path_js += f"""
                    new kakao.maps.Circle({{
                        map: map, center: new kakao.maps.LatLng({r['위도']}, {r['경도']}),
                        radius: 4, strokeWeight: 0, fillColor: '#FF0000', fillOpacity: {opacity}
                    }});
                    """

        map_html = f"""
        <html>
        <head>
            <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
            <style>
                #map {{ width: 100%; height: 650px; border-radius: 15px; }}
                .pulse-marker {{
                    width: 16px; height: 16px; background-color: #FF0000;
                    border: 3px solid #FFFFFF; border-radius: 50%;
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
                function init() {{
                    if (typeof kakao === 'undefined' || !kakao.maps) {{ setTimeout(init, 100); return; }}
                    kakao.maps.load(function() {{
                        var map = new kakao.maps.Map(document.getElementById('map'), {{
                            center: new kakao.maps.LatLng({lat}, {lon}), level: 3
                        }});
                        {other_markers_js} {path_js} {blink_js}
                    }});
                }}
                init();
            </script>
        </body>
        </html>
        """
        components.html(map_html, height=670)

# --- 3. 실행부 ---
if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state['logged_in']:
        app.show_dashboard()
    else:
        app.show_login_page()