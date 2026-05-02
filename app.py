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
            res = self.client.table("users").select("*").eq("school_id", u_id.strip()).execute()
            if res.data:
                user = res.data[0]
                if str(user['password']).strip() == str(pw).strip():
                    return [user]
            return []
        except: return []

    def get_school_list(self, keyword):
        url = "https://open.neis.go.kr/hub/schoolInfo"
        params = {"KEY": self.neis_key, "Type": "json", "pIndex": 1, "pSize": 10, "SCHUL_NM": keyword}
        try:
            res = requests.get(url, params=params).json()
            if "schoolInfo" in res: return res["schoolInfo"][1]["row"]
            return []
        except: return []

    def register(self, u_id, pw, name, addr):
        try:
            check = self.client.table("users").select("school_id").eq("school_id", u_id).execute()
            if len(check.data) > 0: return False, "이미 존재하는 아이디입니다."
            data = {"school_id": u_id, "password": pw, "school_name": name, "address": addr}
            self.client.table("users").insert(data).execute()
            return True, "회원가입 완료!"
        except: return False, "DB 오류"

    def fetch_students(self, school_id):
        """학생 목록과 최신 위치/상태를 함께 가져옴"""
        try:
            q = self.client.table("students").select("*").eq("school_id", school_id).order("student_name").execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

    def fetch_location_logs(self, student_id):
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
        if 'show_signup' not in st.session_state: st.session_state['show_signup'] = False
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
                if st.button("함께하기", use_container_width=True):
                    user = self.db.authenticate(u_id, u_pw)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = user[0]
                        st.rerun()
                    else: st.error("정보를 확인해주세요.")
                st.write("---")
                if st.button("우리 학교 등록하기", use_container_width=True):
                    st.session_state['show_signup'] = True
                    st.rerun()

    def show_signup_page(self):
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.title("📝 학교 가입")
            s_input = st.text_input("학교명 검색")
            if len(s_input) >= 2:
                s_list = self.db.get_school_list(s_input)
                if s_list:
                    opts = {f"{s['SCHUL_NM']} ({s['ORG_RDNMA']})": s for s in s_list}
                    choice = st.selectbox("학교 선택", options=["선택하세요"] + list(opts.keys()))
                    if choice != "선택하세요":
                        sel = opts[choice]
                        u_id = st.text_input("사용할 ID")
                        pw = st.text_input("비밀번호", type="password")
                        if st.button("가입 완료"):
                            ok, msg = self.db.register(u_id, pw, sel['SCHUL_NM'], sel['ORG_RDNMA'])
                            if ok: st.success(msg); st.session_state['show_signup'] = False; st.rerun()
            if st.button("돌아가기"): st.session_state['show_signup'] = False; st.rerun()

    def show_dashboard(self):
        user = st.session_state['user_info']
        st.sidebar.title(f"🏫 {user['school_name']}")
        
        # [해결] 실시간 갱신을 위해 데이터 로드
        df_students = self.db.fetch_students(user['school_id'])
        
        menu = st.sidebar.radio("관리 메뉴", ["실시간 학생 모니터링", "학생 위치 전송 시스템"])
        if st.sidebar.button("로그아웃"): st.session_state['logged_in'] = False; st.rerun()

        if menu == "실시간 학생 모니터링":
            st.title("👁️ 실시간 학생 모니터링")
            if not df_students.empty:
                c1, c2 = st.columns([1, 3])
                with c1:
                    st.subheader("👤 명단")
                    for _, row in df_students.iterrows():
                        # [해결] 실시간 전송 상태 표시 (status 컬럼 기준)
                        # GPS 전송 중이면 초록색, 아니면 빨간색 아이콘
                        status_icon = "🟢" if row.get('status') == "전송중" else "🔴"
                        btn_label = f"{status_icon} {row['student_name']}"
                        
                        if st.button(btn_label, key=f"s_{row['id']}", use_container_width=True):
                            st.session_state['selected_student_id'] = row['id']
                            st.session_state['selected_student_name'] = row['student_name']
                            st.rerun()
                with c2:
                    logs_df = pd.DataFrame()
                    if st.session_state.get('selected_student_id'):
                        logs_df = self.db.fetch_location_logs(st.session_state['selected_student_id'])
                    self.render_kakao_map(df_students, logs_df)
            else: st.info("전송 시스템에서 먼저 이름을 등록해주세요.")

        elif menu == "학생 위치 전송 시스템":
            st.title("📲 학생 위치 전송 시스템")
            with st.container(border=True):
                s_name = st.text_input("학생 이름 입력")
                if st.button("🚀 위치 전송 시작", use_container_width=True, type="primary"):
                    if s_name:
                        st.session_state['tracking_active'] = True
                        st.success(f"{s_name} 학생 전송 시작!")
                    else: st.warning("이름을 입력해주세요.")
                if st.button("⏹️ 전송 중지"):
                    st.session_state['tracking_active'] = False
                    # [해결] 중지 시 상태 업데이트를 위한 JS 호출은 render 내에서 처리
                    st.rerun()
                if st.session_state['tracking_active']:
                    self.render_gps_sender(s_name, user['school_id'])

def render_kakao_map(self, df_students, logs_df):
        """[수정] 기본 위치 제거: 연결 시 깜빡임, 미연결 시 고정 표시"""
        if df_students.empty: return
        
        # 선택된 학생 정보 추출
        selected_id = st.session_state.get('selected_student_id')
        current_student = df_students[df_students['id'].astype(str) == str(selected_id)] if selected_id else pd.DataFrame()
        
        # 1. 중심점 및 표시 좌표 설정 (기본 위치 로직 삭제)
        # 최신 로그가 있으면 그 위치, 없으면 students 테이블의 마지막 저장 위치 사용
        if not logs_df.empty:
            lat, lon = logs_df.iloc[0]['위도'], logs_df.iloc[0]['경도']
        elif not current_student.empty and current_student.iloc[0]['lat'] != 0:
            lat, lon = current_student.iloc[0]['lat'], current_student.iloc[0]['lon']
        else:
            # 데이터가 아예 없는 학생이면 지도를 그리지 않거나 알림만 표시
            st.warning("해당 학생의 위치 기록이 없습니다.")
            return

        kakao_key = st.secrets['kakao']['js_key']
        
        # 2. 모든 학생 마커 표시 (다른 학생들)
        all_markers_js = ""
        for _, r in df_students.iterrows():
            if r['lat'] != 0 and str(r['id']) != str(selected_id):
                all_markers_js += f"new kakao.maps.Marker({{ position: new kakao.maps.LatLng({r['lat']}, {r['lon']}), map: map, title: '{r['student_name']}' }});"

        # 3. [핵심] 연결 상태에 따른 선택 학생 표시 로직
        # logs_df가 비어있지 않고 최신 데이터가 있으면 '깜빡임', 아니면 '고정'
        blink_js = ""
        if not logs_df.empty:
            # 실시간 전송 중인 경우: 깜빡이는 원형 커스텀 오버레이
            blink_js = f"""
            var content = '<div class="pulse-marker"></div>';
            new kakao.maps.CustomOverlay({{
                position: new kakao.maps.LatLng({lat}, {lon}),
                content: content,
                map: map,
                yAnchor: 0.5
            }});
            """
        else:
            # 연결되지 않은 경우: 깜빡임 없는 일반 마커 또는 고정된 원
            blink_js = f"""
            new kakao.maps.Marker({{
                position: new kakao.maps.LatLng({lat}, {lon}),
                map: map,
                title: '{current_student.iloc[0]['student_name']} (마지막 위치)'
            }});
            """

        map_html = f"""
        <html>
        <head>
            <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
            <style>
                #map {{ width: 100%; height: 600px; border-radius: 15px; background: #eee; }}
                .pulse-marker {{
                    width: 20px;
                    height: 20px;
                    background: #FF0000;
                    border: 3px solid #FFFFFF;
                    border-radius: 50%;
                    box-shadow: 0 0 12px rgba(255, 0, 0, 0.8);
                    animation: pulse-ring 1.5s cubic-bezier(0.455, 0.03, 0.515, 0.955) infinite;
                }}
                @keyframes pulse-ring {{
                    0% {{ transform: scale(0.8); box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.7); }}
                    70% {{ transform: scale(1.2); box-shadow: 0 0 0 15px rgba(255, 0, 0, 0); }}
                    100% {{ transform: scale(0.8); box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }}
                }}
            </style>
        </head>
        <body style="margin:0;"><div id="map"></div>
            <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&autoload=false"></script>
            <script>
                function initMap() {{
                    if (typeof kakao === 'undefined' || !kakao.maps) {{
                        setTimeout(initMap, 100);
                        return;
                    }}
                    kakao.maps.load(function() {{
                        var container = document.getElementById('map');
                        var options = {{ center: new kakao.maps.LatLng({lat}, {lon}), level: 3 }};
                        var map = new kakao.maps.Map(container, options);
                        {all_markers_js}
                        {blink_js}
                    }});
                }}
                initMap();
            </script>
        </body></html>
        """
        components.html(map_html, height=620)

# 실행부
if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state.get('logged_in'): app.show_dashboard()
    elif st.session_state.get('show_signup'): app.show_signup_page()
    else: app.show_login_page()